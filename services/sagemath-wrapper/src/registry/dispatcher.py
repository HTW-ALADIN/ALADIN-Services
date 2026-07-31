"""Dispatcher — dispatches an OperationSpec to execution."""

import importlib

import jsonschema
import jsonschema.exceptions

from src.registry.loader import OperationSpec
from src.registry.renderer import render_template
from src.sandbox.executor import run_sandboxed_code


def execute_operation(op: OperationSpec, payload: dict) -> dict:
    """Execute an operation according to its *op* spec with the given *payload*.

    Returns a dict with ``ok``, ``result``, and ``error`` keys.
    """
    # Validate payload against input_schema
    try:
        jsonschema.validate(payload, op.input_schema)
    except jsonschema.exceptions.ValidationError as exc:
        return {"ok": False, "result": None, "error": exc.message}

    if op.kind == "function":
        module_path, func_name = op.function_ref.split(":", 1)
        fn = getattr(importlib.import_module(module_path), func_name)
        try:
            result = fn(**payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "result": None, "error": str(exc)}
        return {"ok": True, "result": result, "error": None}

    if op.kind == "template":
        try:
            code = render_template(op.sage_template, payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "result": None, "error": str(exc)}

        result = run_sandboxed_code(code, timeout_s=op.timeout_s)
        if not result["ok"]:
            return result

        # Check output type
        v = result["result"]
        if op.output_type == "scalar" and not isinstance(v, (bool, int, float)):
            return {"ok": False, "result": None, "error": f"expected scalar, got {type(v).__name__}"}
        if op.output_type == "vector" and not isinstance(v, list):
            return {"ok": False, "result": None, "error": f"expected vector (list), got {type(v).__name__}"}
        if op.output_type == "matrix" and not (isinstance(v, list) and all(isinstance(r, list) for r in v)):
            return {"ok": False, "result": None, "error": f"expected matrix (list of lists), got {type(v).__name__}"}
        if op.output_type == "object" and not isinstance(v, dict):
            return {"ok": False, "result": None, "error": f"expected object (dict), got {type(v).__name__}"}
        if op.output_type == "sat_result" and not (isinstance(v, dict) and "satisfiable" in v):
            return {"ok": False, "result": None, "error": f"expected sat_result (dict with 'satisfiable'), got {type(v).__name__}"}

        return result

    return {"ok": False, "result": None, "error": f"unknown kind '{op.kind}'"}