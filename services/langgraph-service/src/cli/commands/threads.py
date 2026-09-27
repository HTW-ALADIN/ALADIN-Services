from __future__ import annotations

import asyncio
import json

import typer

import main as app_module
from core.checkpointer import get_manager
from core.compiler import CompilerSettings, compile_graph
from core.store import registry


def thread(
    action: str = typer.Argument(..., help="create|state|history|delete"),
    thread_id: str | None = typer.Argument(None, help="Thread id for state/history/delete"),
    graph: str | None = typer.Option(None, "--graph", help="Graph id for thread create"),
    limit: int = typer.Option(20, help="History entry limit"),
) -> None:
    """Manage threads; prints JSON."""
    app_module.ensure_runtime()
    if action == "create":
        if graph is None:
            raise typer.BadParameter("--graph is required for thread create")
        stored = registry.get_graph(graph)
        if stored is None:
            raise typer.BadParameter(f"Unknown graph id {graph!r}.")
        created = registry.create_thread(graph)
        typer.echo(
            json.dumps(
                {
                    "thread_id": created.thread_id,
                    "graph_id": created.graph_id,
                    "created_at": created.created_at,
                },
                indent=2,
            )
        )
    elif action == "state":
        if thread_id is None:
            raise typer.BadParameter("thread_id is required for thread state")
        typer.echo(json.dumps(asyncio.run(_state(thread_id)), indent=2))
    elif action == "history":
        if thread_id is None:
            raise typer.BadParameter("thread_id is required for thread history")
        typer.echo(json.dumps(asyncio.run(_history(thread_id, limit)), indent=2))
    elif action == "delete":
        if thread_id is None:
            raise typer.BadParameter("thread_id is required for thread delete")
        if not registry.delete_thread(thread_id):
            raise typer.BadParameter(f"Unknown thread id {thread_id!r}.")
        typer.echo(json.dumps({"deleted": thread_id}, indent=2))
    else:
        raise typer.BadParameter(
            f"unknown thread action {action!r}; expected create|state|history|delete"
        )


async def _compiled_for(thread_id: str):
    from config import settings

    thread = registry.get_thread(thread_id)
    if thread is None:
        raise typer.BadParameter(f"Unknown thread id {thread_id!r}.")
    stored = registry.get_graph(thread.graph_id)
    if stored is None:
        raise typer.BadParameter(f"Graph {thread.graph_id!r} no longer exists.")
    compiled = compile_graph(
        stored.definition,
        CompilerSettings(
            gateway_base_url=settings.llm_gateway_base_url,
            gateway_api_key=settings.llm_gateway_api_key,
            llm_timeout_seconds=settings.llm_node_timeout_seconds,
            llm_retry_once=settings.llm_retry_once,
            http_timeout_seconds=settings.http_node_timeout_seconds,
            max_tool_response_bytes=settings.max_tool_response_bytes,
        ),
        checkpointer=get_manager().get(),
    )
    return thread, {"configurable": {"thread_id": thread_id}}, compiled


async def _state(thread_id: str) -> dict:
    thread, config, compiled = await _compiled_for(thread_id)
    snapshot = await compiled.aget_state(config)
    values = snapshot.values if isinstance(snapshot.values, dict) else {"result": snapshot.values}
    if isinstance(values, dict) and "data" in values and isinstance(values["data"], dict):
        values = values["data"]
    return {
        "thread_id": thread_id,
        "graph_id": thread.graph_id,
        "values": values,
        "next": list(snapshot.next),
    }


async def _history(thread_id: str, limit: int) -> dict:
    _, config, compiled = await _compiled_for(thread_id)
    snapshots = [
        s async for s in compiled.aget_state_history(config, limit=max(1, min(limit, 100)))
    ]
    entries = []
    for s in snapshots:
        values = s.values if isinstance(s.values, dict) else {"result": s.values}
        if isinstance(values, dict) and "data" in values and isinstance(values["data"], dict):
            values = values["data"]
        entries.append({"values": values, "next": list(s.next)})
    return {"thread_id": thread_id, "history": entries}
