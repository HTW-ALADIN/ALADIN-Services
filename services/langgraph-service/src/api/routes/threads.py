"""Thread endpoints: create/inspect/delete execution threads."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from core.checkpointer import get_manager
from core.compiler import CompilerSettings, compile_graph
from core.store import registry


class CreateThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph_id: str


router = APIRouter()


@router.post("/v1/threads", status_code=201)
async def create_thread(request: CreateThreadRequest) -> JSONResponse:
    stored = registry.get_graph(request.graph_id)
    if stored is None:
        return JSONResponse(
            status_code=404, content={"detail": f"Unknown graph id {request.graph_id!r}."}
        )
    thread = registry.create_thread(request.graph_id)
    return JSONResponse(
        status_code=201,
        content={
            "thread_id": thread.thread_id,
            "graph_id": thread.graph_id,
            "created_at": thread.created_at,
        },
    )


@router.get("/v1/threads/{thread_id}/state")
async def get_thread_state(thread_id: str) -> JSONResponse:
    from config import settings

    thread = registry.get_thread(thread_id)
    if thread is None:
        return JSONResponse(
            status_code=404, content={"detail": f"Unknown thread id {thread_id!r}."}
        )
    stored = registry.get_graph(thread.graph_id)
    if stored is None:
        return JSONResponse(
            status_code=410,
            content={
                "detail": f"Graph {thread.graph_id!r} for thread {thread_id!r} no longer exists."
            },
        )
    try:
        checkpointer = get_manager().get()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    from config import settings as _settings

    compiled = compile_graph(
        stored.definition,
        CompilerSettings(
            gateway_base_url=_settings.llm_gateway_base_url,
            gateway_api_key=_settings.llm_gateway_api_key,
            llm_timeout_seconds=_settings.llm_node_timeout_seconds,
            llm_retry_once=_settings.llm_retry_once,
            http_timeout_seconds=_settings.http_node_timeout_seconds,
            max_tool_response_bytes=_settings.max_tool_response_bytes,
        ),
        checkpointer=checkpointer,
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.recursion_limit,
    }
    try:
        snapshot = await compiled.aget_state(config)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": f"state lookup failed: {exc}"})
    values = snapshot.values if isinstance(snapshot.values, dict) else {"result": snapshot.values}
    data = values.get("data", values) if isinstance(values, dict) else values
    if not isinstance(data, dict):
        data = {"result": data}
    return JSONResponse(
        status_code=200,
        content={
            "thread_id": thread_id,
            "graph_id": thread.graph_id,
            "values": data,
            "next": list(snapshot.next),
        },
    )


@router.get("/v1/threads/{thread_id}/history")
async def get_thread_history(thread_id: str, limit: int = 20) -> JSONResponse:
    thread = registry.get_thread(thread_id)
    if thread is None:
        return JSONResponse(
            status_code=404, content={"detail": f"Unknown thread id {thread_id!r}."}
        )
    stored = registry.get_graph(thread.graph_id)
    if stored is None:
        return JSONResponse(
            status_code=410,
            content={
                "detail": f"Graph {thread.graph_id!r} for thread {thread_id!r} no longer exists."
            },
        )
    limit = max(1, min(limit, 100))
    try:
        checkpointer = get_manager().get()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    from config import settings as _settings

    compiled = compile_graph(
        stored.definition,
        CompilerSettings(
            gateway_base_url=_settings.llm_gateway_base_url,
            gateway_api_key=_settings.llm_gateway_api_key,
            llm_timeout_seconds=_settings.llm_node_timeout_seconds,
            llm_retry_once=_settings.llm_retry_once,
            http_timeout_seconds=_settings.http_node_timeout_seconds,
            max_tool_response_bytes=_settings.max_tool_response_bytes,
        ),
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshots = [s async for s in compiled.aget_state_history(config, limit=limit)]
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": f"history lookup failed: {exc}"})
    entries = []
    for snapshot in snapshots:
        values = (
            snapshot.values if isinstance(snapshot.values, dict) else {"result": snapshot.values}
        )
        if isinstance(values, dict) and "data" in values and isinstance(values["data"], dict):
            values = values["data"]
        checkpoint_id = None
        if isinstance(snapshot.config, dict):
            configurable = snapshot.config.get("configurable", {})
            if isinstance(configurable, dict):
                checkpoint_id = configurable.get("checkpoint_id")
        entries.append(
            {
                "checkpoint_id": checkpoint_id,
                "values": values,
                "next": list(snapshot.next),
            }
        )
    return JSONResponse(status_code=200, content={"thread_id": thread_id, "history": entries})


@router.delete("/v1/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: str) -> JSONResponse:
    if registry.get_thread(thread_id) is None:
        return JSONResponse(
            status_code=404, content={"detail": f"Unknown thread id {thread_id!r}."}
        )
    await get_manager().get().adelete_thread(thread_id)
    registry.delete_thread(thread_id)
    return JSONResponse(status_code=204, content=None)
