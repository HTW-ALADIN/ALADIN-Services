from __future__ import annotations

from importlib import import_module

from fastapi import FastAPI, HTTPException

from graph_tool_sidecar.generation import generate
from graph_tool_sidecar.models import SidecarGraph, SidecarRequest

app = FastAPI(
    title="Graph Tool Generation Sidecar",
    description="Internal graph-tool adapter for the Unified Graph Generation Service.",
    version="0.2.0",
)


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
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="graph-tool is unavailable") from exc
    except (AssertionError, IndexError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"graph-tool generation failed: {exc}") from exc
