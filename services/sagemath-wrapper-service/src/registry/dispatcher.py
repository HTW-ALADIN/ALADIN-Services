"""Dispatcher — dispatches an OperationSpec to execution.

This is the single execution entry point. It validates input, runs the
operation (function or template) in a sandboxed subprocess with the
configured timeout, and returns a uniform ``{"ok": bool, "result": ..., "error": ...}``
dict. All errors (validation, execution, output-type) are signalled via
``ok=False`` — never via exceptions.
"""

import logging

import jinja2
import jinja2.sandbox
import jsonschema
import jsonschema.exceptions

from src.registry.loader import OperationSpec
from src.sandbox.executor import run_code, run_function

logger = logging.getLogger(__name__)


def render_template(sage_template: str, values: dict) -> str:
    """Render a Jinja2 template string with *values* using the sandboxed env.

    ═══════════════════════════════════════════════════════════════════════
    IMPORTANT: All user-supplied ``{{ var }}`` values MUST be interpolated
    through the ``|sage_literal`` filter (which applies ``repr()``) to
    prevent code injection.  Never use ``|safe`` or bare ``{{ var }}`` with
    user data.
    ═══════════════════════════════════════════════════════════════════════

    * Template syntax uses ``{{ ...|sage_literal }}`` for safe value insertion.
    * ``SandboxedEnvironment`` blocks dangerous attribute access (``__class__``,
      ``__mro__``, ``__subclasses__``, etc.).
    * ``StrictUndefined`` raises ``jinja2.UndefinedError`` (converted to
      ``ValueError``) for missing keys.
    * Extra keys in *values* that are not referenced by the template are silently
      ignored.

    Returns the rendered code string (execution is handled separately by
    :func:`src.sandbox.executor.run_code`).
    """
    env = jinja2.sandbox.SandboxedEnvironment(
        undefined=jinja2.StrictUndefined,
    )
    env.filters["sage_literal"] = repr

    try:
        return env.from_string(sage_template).render(**values)
    except jinja2.UndefinedError as exc:
        raise ValueError(str(exc)) from exc
    except jinja2.security.SecurityError as exc:
        raise RuntimeError(f"template blocked by sandbox: {exc}") from exc


def _apply_schema_defaults(cleaned: dict, input_schema: dict) -> dict:
    """Fill in JSON-Schema ``default`` values for properties missing from
    *cleaned*.

    ``jsonschema.validate`` never mutates its input or applies ``default``
    values on the caller's behalf. The HTTP API layer (``src.api.dynamic_routes``)
    separately fills defaults via generated Pydantic models, but the CLI and
    any other direct ``execute_operation`` caller go through this dispatcher
    only — so defaults must be applied here as well, otherwise omitting a
    documented-as-optional field raises a ``TypeError`` deep inside the
    sandboxed function instead of using its declared default.
    """
    properties = input_schema.get("properties", {}) or {}
    for name, schema in properties.items():
        if name not in cleaned and "default" in schema:
            cleaned[name] = schema["default"]
    return cleaned


def execute_operation(op: OperationSpec, payload: dict) -> dict:
    """Execute an operation according to its *op* spec with the given *payload*.

    Returns a dict with ``ok``, ``result``, and ``error`` keys.
    """
    # Validate payload against input_schema
    # Strip None values only for keys NOT in `required`, so legitimately-null
    # required fields are preserved and validated.
    required = set(op.input_schema.get("required", []) or [])
    cleaned = {
        k: v for k, v in payload.items()
        if v is not None or k in required
    }
    cleaned = _apply_schema_defaults(cleaned, op.input_schema)
    try:
        jsonschema.validate(cleaned, op.input_schema)
    except jsonschema.exceptions.ValidationError as exc:
        logger.warning("validation failed for %s: %s", op.id, exc.message)
        return {"ok": False, "result": None, "error": exc.message}

    timeout = op.timeout_s

    if op.kind == "function":
        result = run_function(op.function_ref, cleaned, timeout_s=timeout)
    elif op.kind == "template":
        try:
            code = render_template(op.sage_template, cleaned)
        except (ValueError, RuntimeError) as exc:
            logger.warning("template render failed for %s: %s", op.id, exc)
            return {"ok": False, "result": None, "error": "invalid input"}
        result = run_code(code, timeout_s=timeout)
    else:
        return {"ok": False, "result": None, "error": f"unknown kind '{op.kind}'"}

    if not result["ok"]:
        logger.warning("execution failed for %s: %s", op.id, result.get("error"))
        return result

    # Output-type check — applies to both function and template results.
    # `object` is permissive (accepts any JSON-safe value) because polymorphic
    # operations (e.g. maxima.evaluate) return strings, floats, lists, or dicts.
    v = result["result"]
    if op.output_type == "scalar" and not isinstance(v, (bool, int, float, str)):
        return {"ok": False, "result": None, "error": f"expected scalar, got {type(v).__name__}"}
    if op.output_type == "vector" and not isinstance(v, list):
        return {"ok": False, "result": None, "error": f"expected vector (list), got {type(v).__name__}"}
    if op.output_type == "matrix" and not (
        isinstance(v, list) and len(v) > 0 and all(isinstance(r, list) for r in v)
    ):
        return {"ok": False, "result": None, "error": f"expected matrix (non-empty list of lists), got {type(v).__name__}"}
    if op.output_type == "sat_result" and not (isinstance(v, dict) and "satisfiable" in v):
        return {"ok": False, "result": None, "error": f"expected sat_result (dict with 'satisfiable'), got {type(v).__name__}"}

    return result