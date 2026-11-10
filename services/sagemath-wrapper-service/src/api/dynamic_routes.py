"""Dynamic route registration — creates FastAPI endpoints from OperationSpec."""

import typing
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, create_model

from src.registry.dispatcher import execute_operation
from src.registry.loader import OperationSpec
from src.sandbox.executor import BUSY_ERROR


def _json_schema_to_python_type(schema: dict, op_id: str = "?") -> type:
    """Recursively convert a JSON Schema snippet to a Python type."""
    enum_vals = schema.get("enum")
    if enum_vals is not None:
        if not enum_vals:
            # Empty enum — fall back to str (accept any string)
            return str
        try:
            return Literal[*tuple(enum_vals)]
        except Exception as exc:
            raise ValueError(f"op '{op_id}': bad schema: {exc}") from exc

    mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
    }
    js_type = schema.get("type")
    if js_type == "array":
        items = schema.get("items", {})
        inner = _json_schema_to_python_type(items, op_id)
        return list[inner]
    if js_type == "object":
        addl = schema.get("additionalProperties", {})
        if addl:
            inner = _json_schema_to_python_type(addl, op_id)
            return dict[str, inner]
        return dict[str, typing.Any]
    return mapping.get(js_type, typing.Any)


def _create_request_model(op_id: str, schema: dict) -> type[BaseModel]:
    """Dynamically create a Pydantic request model from a JSON Schema."""
    fields: dict[str, tuple] = {}
    required = set(schema.get("required", []) or [])
    properties = schema.get("properties", {}) or {}

    for field_name, field_schema in properties.items():
        py_type = _json_schema_to_python_type(field_schema, op_id)
        has_default = "default" in field_schema
        default_val = field_schema.get("default")

        if field_name in required:
            fields[field_name] = (py_type, ...)
        elif has_default:
            # Use the actual default value (including falsy ones like 0, false, "")
            fields[field_name] = (py_type, default_val)
        else:
            fields[field_name] = (py_type | None, None)

    return create_model(f"{op_id}_request", **fields)




def register_routes(app: FastAPI, operations: list[OperationSpec]) -> None:
    """Register POST endpoints for every *operations* on *app*.

    Each operation gets a route at ``/v1/{op.id.replace('.', '/')}``.
    Override handling:
    - ``{"ok": True, "result": <value>}`` → 200 with the raw result
    - ``{"ok": False, "error": "busy"}`` → 503 with ``Retry-After`` header
    - ``{"ok": False, "error": <msg>}`` → 400 with ``{"detail": msg}``
    """
    router = APIRouter(prefix="/v1", tags=["operations"])

    for op in operations:
        path = "/" + op.id.replace(".", "/")
        req_model = _create_request_model(op.id, op.input_schema)
        _register_one(router, path, op, req_model)

    app.include_router(router)


def _register_one(router: APIRouter, path: str, op: OperationSpec, req_model: type[BaseModel]) -> None:
    """Register a single endpoint — factored out to capture *op* by value."""

    @router.post(path, name=op.id)
    def _handler(body: req_model) -> typing.Any:  # type: ignore[valid-type]
        payload = body.model_dump()
        result = execute_operation(op, payload)
        if not result["ok"]:
            if result["error"] == BUSY_ERROR:
                raise HTTPException(
                    status_code=503,
                    detail="server busy, please retry",
                    headers={"Retry-After": "2"},
                )
            raise HTTPException(status_code=400, detail=result["error"])
        return result["result"]

    _handler.__name__ = f"handle_{op.id.replace('.', '_')}"
    _handler.__qualname__ = _handler.__name__