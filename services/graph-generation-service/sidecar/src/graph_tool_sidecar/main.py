from __future__ import annotations

from importlib import import_module

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response

from graph_safety.http import BodyLimitMiddleware, problem
from graph_safety.limits import ResourceLimitError
from graph_tool_sidecar.generation import generate_isolated as generate
from graph_tool_sidecar.models import SidecarGraph, SidecarRequest

app = FastAPI(
    title="Graph Tool Generation Sidecar",
    description="Internal graph-tool adapter for the Unified Graph Generation Service.",
    version="0.2.0",
)
app.add_middleware(BodyLimitMiddleware)


async def resource_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ResourceLimitError):
        raise exc
    return problem(exc, request.url.path)


app.add_exception_handler(ResourceLimitError, resource_error_handler)


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    try:
        import_module("graph_tool")
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="graph-tool is unavailable") from exc
    return {"status": "ok"}


@app.post("/v1/generate", response_model=SidecarGraph, include_in_schema=False)
def generate_graph(request: SidecarRequest) -> SidecarGraph:
    try:
        return generate(request)
    except ResourceLimitError:
        raise
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="graph-tool is unavailable") from exc
    except (AssertionError, IndexError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"graph-tool generation failed: {exc}") from exc
