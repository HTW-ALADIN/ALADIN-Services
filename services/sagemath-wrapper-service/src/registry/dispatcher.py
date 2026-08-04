"""Dispatcher — dispatches an OperationSpec to execution.

This is the single execution entry point. It validates input, runs the
operation (function or template) in a sandboxed subprocess with the
configured timeout, and returns a uniform ``{"ok": bool, "result": ..., "error": ...}``
dict. All errors (validation, execution, output-type) are signalled via
``ok=False`` — never via exceptions.
"""

import jinja2
import jinja2.sandbox
import jsonschema
import jsonschema.exceptions

from src.registry.loader import OperationSpec
from src.sandbox.executor import run_code, run_function


def render_template(sage_template: str, values: dict) -> str:
    """Render a Jinja2 template string with *values* using the sandboxed env.

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


def execute_operation(op: OperationSpec, payload: dict) -> dict:
    """Execute an operation according to its *op* spec with the given *payload*.

    Returns a dict with ``ok``, ``result``, and ``error`` keys.
    """
    # Validate payload against input_schema
    cleaned = {k: v for k, v in payload.items() if v is not None}
    try:
        jsonschema.validate(cleaned, op.input_schema)
    except jsonschema.exceptions.ValidationError as exc:
        return {"ok": False, "result": None, "error": exc.message}

    timeout = op.timeout_s

    if op.kind == "function":
        result = run_function(op.function_ref, cleaned, timeout_s=timeout)
    elif op.kind == "template":
        try:
            code = render_template(op.sage_template, cleaned)
        except (ValueError, RuntimeError) as exc:
            return {"ok": False, "result": None, "error": str(exc)}
        result = run_code(code, timeout_s=timeout)
    else:
        return {"ok": False, "result": None, "error": f"unknown kind '{op.kind}'"}

    if not result["ok"]:
        return result

    # Output-type check — applies to both function and template results.
    # `object` is permissive (accepts any JSON-safe value) because polymorphic
    # operations (e.g. maxima.evaluate) return strings, floats, lists, or dicts.
    v = result["result"]
    if op.output_type == "scalar" and not isinstance(v, (bool, int, float, str)):
        return {"ok": False, "result": None, "error": f"expected scalar, got {type(v).__name__}"}
    if op.output_type == "vector" and not isinstance(v, list):
        return {"ok": False, "result": None, "error": f"expected vector (list), got {type(v).__name__}"}
    if op.output_type == "matrix" and not (isinstance(v, list) and all(isinstance(r, list) for r in v)):
        return {"ok": False, "result": None, "error": f"expected matrix (list of lists), got {type(v).__name__}"}
    if op.output_type == "sat_result" and not (isinstance(v, dict) and "satisfiable" in v):
        return {"ok": False, "result": None, "error": f"expected sat_result (dict with 'satisfiable'), got {type(v).__name__}"}

    return result