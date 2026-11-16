"""Run orchestration: compile-once-per-run execution against the checkpointer."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from langgraph.errors import GraphRecursionError

from core.checkpointer import get_manager
from core.compiler import CompilerSettings, compile_graph
from core.errors import CheckpointerNotReadyError, NodeExecutionError
from core.limits import get_limiter
from core.store import registry


def _compiler_settings() -> CompilerSettings:
    from config import settings

    return CompilerSettings(
        gateway_base_url=settings.llm_gateway_base_url,
        gateway_api_key=settings.llm_gateway_api_key,
        llm_timeout_seconds=settings.llm_node_timeout_seconds,
        llm_retry_once=settings.llm_retry_once,
        http_timeout_seconds=settings.http_node_timeout_seconds,
        max_tool_response_bytes=settings.max_tool_response_bytes,
        http_internal_host_allowlist=frozenset(settings.http_internal_host_allowlist.split(",")),
    )


def thread_config(thread_id: str, recursion_limit: int) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }


async def invoke_run(thread_id: str, run_input: dict[str, Any]) -> dict[str, Any]:
    """Execute one synchronous run; raises domain errors mapped by routes."""
    from config import settings

    thread = registry.get_thread(thread_id)
    if thread is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Unknown thread id {thread_id!r}.")
    stored = registry.get_graph(thread.graph_id)
    if stored is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=410,
            detail=f"Graph {thread.graph_id!r} for thread {thread_id!r} no longer exists.",
        )
    try:
        checkpointer = get_manager().get()
    except CheckpointerNotReadyError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc

    compiled = compile_graph(stored.definition, _compiler_settings(), checkpointer=checkpointer)
    limiter = get_limiter()
    config = thread_config(thread_id, settings.recursion_limit)
    async with limiter.acquire():
        try:
            wrapped = await limiter.run_with_timeout(
                compiled.ainvoke({"data": dict(run_input)}, config)
            )
        except NodeExecutionError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=502, detail=exc.to_payload()) from exc
        except GraphRecursionError as exc:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=502,
                detail={
                    "node_id": None,
                    "message": f"graph exceeded recursion limit {settings.recursion_limit}: {exc}",
                },
            ) from exc
    if not isinstance(wrapped, dict):
        return {"result": wrapped}
    data = wrapped.get("data", wrapped)
    output = data if isinstance(data, dict) else {"result": data}
    if not isinstance(output, dict):
        output = {"result": output}
    return output


async def stream_run(thread_id: str, run_input: dict[str, Any]):
    """Yield SSE-ready event dicts for one streaming run."""
    from config import settings

    thread = registry.get_thread(thread_id)
    if thread is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Unknown thread id {thread_id!r}.")
    stored = registry.get_graph(thread.graph_id)
    if stored is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=410,
            detail=f"Graph {thread.graph_id!r} for thread {thread_id!r} no longer exists.",
        )
    try:
        checkpointer = get_manager().get()
    except CheckpointerNotReadyError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc

    compiled = compile_graph(stored.definition, _compiler_settings(), checkpointer=checkpointer)
    limiter = get_limiter()
    config = thread_config(thread_id, settings.recursion_limit)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)

    async def _produce():
        stream = compiled.astream({"data": dict(run_input)}, config, stream_mode="updates")
        try:
            async for event in stream:
                unwrapped = {
                    node_id: update.get("data", update) if isinstance(update, dict) else update
                    for node_id, update in event.items()
                }
                await queue.put(unwrapped)
        finally:
            await stream.aclose()

    async def _run():
        async with limiter.acquire():
            await limiter.run_with_timeout(_produce())

    task = asyncio.create_task(_run())
    task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
    try:
        while True:
            if task.done():
                task.result()
                if queue.empty():
                    break
                yield queue.get_nowait()
                continue
            pending_event = asyncio.create_task(queue.get())
            try:
                done, _ = await asyncio.wait(
                    {task, pending_event}, return_when=asyncio.FIRST_COMPLETED
                )
                if task in done:
                    task.result()
                if pending_event in done:
                    yield pending_event.result()
            finally:
                if not pending_event.done():
                    pending_event.cancel()
                    with suppress(asyncio.CancelledError):
                        await pending_event
    except NodeExecutionError as exc:
        yield {"__error__": exc.to_payload()}
    except GraphRecursionError as exc:
        yield {
            "__error__": {
                "node_id": None,
                "message": f"graph exceeded recursion limit {settings.recursion_limit}: {exc}",
            }
        }
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
