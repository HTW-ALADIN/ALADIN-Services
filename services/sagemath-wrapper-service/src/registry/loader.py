"""Registry loader — loads OperationSpec from YAML files with validation."""

import importlib
import os
import warnings
from typing import Literal

import jsonschema
import pydantic
import yaml

_VALID_OUTPUT_TYPES = frozenset({"scalar", "vector", "matrix", "object", "sat_result"})


class OperationSpec(pydantic.BaseModel):
    """Specification for a single registry operation."""

    id: str
    summary: str
    kind: Literal["function", "template"]
    input_schema: dict
    output_type: Literal["scalar", "vector", "matrix", "object", "sat_result"]
    timeout_s: float
    function_ref: str | None = None
    sage_template: str | None = None


def load_registry(path: str) -> list[OperationSpec]:
    """Load all ``*.yaml`` files from *path* (file or directory).

    Validates each entry: JSON Schema, function_ref format, duplicate IDs.
    By default, ``function_ref`` module imports are **lazy** (format-only
    validation) so the OpenAPI export works without SageMath at import time.
    Set ``SAGE_STRICT_REGISTRY=1`` to enable full import validation at
    load time.
    Returns a list of :class:`OperationSpec` objects.
    """
    strict = os.environ.get("SAGE_STRICT_REGISTRY", "") == "1"

    if os.path.isfile(path):
        paths = [path]
    elif os.path.isdir(path):
        paths = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.endswith((".yaml", ".yml"))
        )
    else:
        raise ValueError(f"registry path '{path}' is neither a file nor a directory")

    specs: list[OperationSpec] = []
    seen_ids: set[str] = set()

    for p in paths:
        with open(p) as fh:
            entries = yaml.safe_load(fh) or []
        for entry in entries:
            kind = entry.get("kind")
            function_ref = entry.get("function_ref")
            sage_template = entry.get("sage_template")
            eid = entry.get("id", "?")

            if kind == "function" and not function_ref:
                raise ValueError(f"entry '{eid}': kind=function requires function_ref")
            if kind == "template" and not sage_template:
                raise ValueError(f"entry '{eid}': kind=template requires sage_template")

            output_type = entry.get("output_type")
            if output_type not in _VALID_OUTPUT_TYPES:
                raise ValueError(
                    f"entry '{eid}': invalid output_type '{output_type}'. "
                    f"valid: {', '.join(sorted(_VALID_OUTPUT_TYPES))}"
                )

            try:
                jsonschema.Draft202012Validator.check_schema(entry.get("input_schema", {}))
            except jsonschema.SchemaError as exc:
                raise ValueError(f"input_schema is not a valid JSON Schema: {exc}") from exc

            if function_ref:
                try:
                    module_path, func_name = function_ref.split(":", 1)
                except ValueError:
                    raise ValueError(
                        f"invalid function_ref format '{function_ref}' — expected 'module:function'"
                    ) from None
                if strict:
                    try:
                        mod = importlib.import_module(module_path)
                    except ImportError as exc:
                        raise ValueError(
                            f"function_ref module '{module_path}' cannot be imported: {exc}"
                        ) from exc
                    if not hasattr(mod, func_name):
                        raise ValueError(
                            f"function_ref '{func_name}' not found in module '{module_path}'"
                        )
                else:
                    # Lazy mode: log a warning on import failure, don't crash
                    try:
                        mod = importlib.import_module(module_path)
                        if not hasattr(mod, func_name):
                            warnings.warn(
                                f"function_ref '{func_name}' not found in module '{module_path}'"
                            )
                    except ImportError:
                        warnings.warn(
                            f"function_ref module '{module_path}' cannot be imported "
                            f"(set SAGE_STRICT_REGISTRY=1 to make this an error)"
                        )

            spec = OperationSpec(**entry)
            if spec.id in seen_ids:
                raise ValueError(f"duplicate operation id '{spec.id}' in registry")
            seen_ids.add(spec.id)
            specs.append(spec)

    return specs