"""Graph definition endpoints: validate-only DSL and registry."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.dsl import GraphDefinition
from core.store import registry
from core.url_safety import UnsafeUrlError, assert_safe_url

router = APIRouter()


class GraphListItem(BaseModel):
    graph_id: str
    name: str
    created_at: str


class GraphListResponse(BaseModel):
    graphs: list[GraphListItem]


@router.post("/v1/graphs", status_code=201)
async def create_graph(request: Request) -> JSONResponse:
    from config import settings

    raw = await request.body()
    if len(raw) > settings.max_graph_bytes:
        return JSONResponse(
            status_code=413,
            content={"detail": f"graph definition exceeds {settings.max_graph_bytes} bytes"},
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return JSONResponse(status_code=400, content={"detail": f"invalid JSON: {exc}"})
    try:
        definition = GraphDefinition.model_validate(payload)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": f"invalid graph definition: {exc}"})

    for node in definition.nodes:
        if node.type == "http":
            try:
                assert_safe_url(node.url)
            except UnsafeUrlError as exc:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"http node {node.id!r} has unsafe URL: {exc}"},
                )

    stored = registry.create_graph(definition)
    return JSONResponse(
        status_code=201,
        content={
            "graph_id": stored.graph_id,
            "name": stored.definition.name,
            "created_at": stored.created_at,
        },
    )


@router.get("/v1/graphs", response_model=GraphListResponse)
async def list_graphs() -> GraphListResponse:
    return GraphListResponse(
        graphs=[
            GraphListItem(graph_id=g.graph_id, name=g.definition.name, created_at=g.created_at)
            for g in registry.list_graphs()
        ]
    )


@router.get("/v1/graphs/{graph_id}")
async def get_graph(graph_id: str) -> JSONResponse:
    stored = registry.get_graph(graph_id)
    if stored is None:
        return JSONResponse(status_code=404, content={"detail": f"Unknown graph id {graph_id!r}."})
    payload: dict[str, Any] = {
        "graph_id": stored.graph_id,
        "name": stored.definition.name,
        "created_at": stored.created_at,
        "definition": stored.definition.model_dump(mode="json"),
    }
    return JSONResponse(status_code=200, content=payload)


@router.delete("/v1/graphs/{graph_id}", status_code=204)
async def delete_graph(graph_id: str) -> JSONResponse:
    if not registry.delete_graph(graph_id):
        return JSONResponse(status_code=404, content={"detail": f"Unknown graph id {graph_id!r}."})
    return JSONResponse(status_code=204, content=None)
