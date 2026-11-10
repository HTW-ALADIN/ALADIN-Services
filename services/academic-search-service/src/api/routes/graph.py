from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas.graph import GraphEdgeSchema, GraphRequest, GraphResponse
from core import graph_service
from core.pagination import InvalidCursorError

router = APIRouter()


@router.post("/v1/graph", response_model=GraphResponse)
async def graph(request: GraphRequest) -> GraphResponse:
    if request.cursor:
        try:
            page = await graph_service.advance(request.cursor, request.credentials)
        except InvalidCursorError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}") from exc
    else:
        if not request.seeds:
            raise HTTPException(
                status_code=400, detail="seeds must not be empty when no cursor is supplied"
            )
        page = await graph_service.start(
            seeds=[(s.provider, s.paper_id) for s in request.seeds],
            direction=request.direction,
            max_depth=request.max_depth,
            max_nodes_per_level=request.max_nodes_per_level,
            max_total_nodes=request.max_total_nodes,
            credentials=request.credentials,
            dedup_enabled=request.dedup_enabled,
        )

    return GraphResponse(
        nodes=page.nodes,
        edges=[GraphEdgeSchema(from_id=e.from_id, to_id=e.to_id, type=e.type) for e in page.edges],
        depth_reached=page.depth_reached,
        max_depth=page.max_depth,
        done=page.done,
        cursor=page.cursor,
        truncated=page.truncated,
        stats=page.stats,
    )
