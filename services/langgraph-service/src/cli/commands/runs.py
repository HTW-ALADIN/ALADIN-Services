from __future__ import annotations

import asyncio
import json

import typer

from cli.runtime import runtime
from core.runner import invoke_run, stream_run


def run(
    action: str = typer.Argument(..., help="invoke|stream"),
    thread_id: str = typer.Argument(..., help="Thread id to run"),
    input: str = typer.Option("{}", help="JSON run input object"),
) -> None:
    """Invoke a thread run (invoke) or print SSE-style frames (stream); prints JSON."""
    asyncio.run(_run(action, thread_id, input))


async def _run(action: str, thread_id: str, input: str) -> None:
    async with runtime():
        await _handle_run(action, thread_id, input)


async def _handle_run(action: str, thread_id: str, input: str) -> None:
    payload = json.loads(input)
    if not isinstance(payload, dict):
        raise typer.BadParameter("--input must be a JSON object")
    if action == "invoke":
        output = await invoke_run(thread_id, payload)
        typer.echo(json.dumps({"thread_id": thread_id, "output": output}, indent=2))
    elif action == "stream":
        await _print_stream(thread_id, payload)
    else:
        raise typer.BadParameter(f"unknown run action {action!r}; expected invoke|stream")


async def _print_stream(thread_id: str, payload: dict) -> None:
    async for event in stream_run(thread_id, payload):
        typer.echo(json.dumps(event))
