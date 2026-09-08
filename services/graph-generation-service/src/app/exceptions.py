from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.catalog import ALGORITHM_SCHEMAS
from app.schemas import RequestParameterError


class GraphExportError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class GraphBackendError(Exception):
    def __init__(self, backend: str, reason: str, *, status_code: int) -> None:
        self.backend = backend
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


DISCRIMINATOR_VALUES = set(ALGORITHM_SCHEMAS)
DISCRIMINATOR_VALUES.update(
    backend for _request_schema, variants in ALGORITHM_SCHEMAS.values() for backend, _params_schema in variants
)


def _clean_discriminator(discriminator: object) -> str | None:
    if not isinstance(discriminator, str):
        return None

    return discriminator.strip("'\"").split(".")[-1]


def _invalid_param_name(error: dict[str, Any]) -> str:
    context = error.get("ctx")
    if isinstance(context, dict):
        parameter_error = context.get("error")
        if isinstance(parameter_error, RequestParameterError):
            return parameter_error.parameter_name

        discriminator = _clean_discriminator(context.get("discriminator"))
        if discriminator is not None:
            return discriminator

    loc = [str(part) for part in error.get("loc", ()) if part != "body"]
    if "algorithm" in loc:
        return "algorithm"
    if "backend" in loc:
        return "backend"

    filtered = [part for part in loc if part not in DISCRIMINATOR_VALUES]
    if not filtered:
        return "body"

    return ".".join(filtered)


def _invalid_param_reason(error: dict[str, Any]) -> str:
    message = error.get("msg")
    if isinstance(message, str) and message:
        return message

    return "Invalid request parameter."


async def request_validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc

    invalid_params = [
        {
            "name": _invalid_param_name(error),
            "reason": _invalid_param_reason(error),
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=400,
        media_type="application/problem+json",
        content={
            "type": "https://api.aladin.local/problems/request-validation",
            "title": "Invalid request body",
            "status": 400,
            "detail": "The graph generation request failed validation.",
            "instance": str(request.url.path),
            "invalidParams": invalid_params,
        },
    )


async def graph_export_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, GraphExportError):
        raise exc

    return JSONResponse(
        status_code=400,
        media_type="application/problem+json",
        content={
            "type": "https://api.aladin.local/problems/graph-export",
            "title": "Graph export failed",
            "status": 400,
            "detail": exc.reason,
            "instance": str(request.url.path),
            "invalidParams": [{"name": "format", "reason": exc.reason}],
        },
    )


async def graph_backend_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, GraphBackendError):
        raise exc

    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": "https://api.aladin.local/problems/graph-backend",
            "title": "Graph backend failed",
            "status": exc.status_code,
            "detail": exc.reason,
            "instance": str(request.url.path),
            "invalidParams": [{"name": "backend", "reason": f"{exc.backend}: {exc.reason}"}],
        },
    )
