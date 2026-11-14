"""Run endpoints: synchronous invoke plus SSE streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from core.errors import RunBusyError, RunTimeoutError
from core.runner import invoke_run, stream_run

router = APIRouter()


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: dict = {}


@router.post("/v1/threads/{thread_id}/runs")
async def invoke_thread_run(thread_id: str, request: RunRequest) -> JSONResponse:
    from fastapi import HTTPException

    from config import settings

    raw = json.dumps(request.input)
    if len(raw.encode("utf-8")) > settings.max_input_bytes:
        return JSONResponse(
            status_code=413,
            content={"detail": f"run input exceeds {settings.max_input_bytes} bytes"},
        )
    try:
        output = await invoke_run(thread_id, dict(request.input))
    except RunBusyError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    except RunTimeoutError as exc:
        return JSONResponse(status_code=504, content={"detail": str(exc)})
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    encoded = json.dumps(output).encode("utf-8")
    if len(encoded) > settings.max_output_bytes:
        return JSONResponse(
            status_code=502,
            content={"detail": f"run output exceeds {settings.max_output_bytes} bytes"},
        )
    return JSONResponse(status_code=200, content={"thread_id": thread_id, "output": output})


@router.post("/v1/threads/{thread_id}/runs:stream")
async def stream_thread_run(thread_id: str, request: RunRequest) -> StreamingResponse:
    from config import settings

    raw = json.dumps(request.input)
    if len(raw.encode("utf-8")) > settings.max_input_bytes:

        async def _too_large():
            yield f"data: {json.dumps({'error': 'run input too large'})}\n\n"

        return StreamingResponse(_too_large(), media_type="text/event-stream")

    async def _events():
        from fastapi import HTTPException

        try:
            async for event in stream_run(thread_id, dict(request.input)):
                if "__error__" in event:
                    yield f"event: error\ndata: {json.dumps(event['__error__'])}\n\n"
                    return
                for node_id, update in event.items():
                    frame = {"node": node_id, "update": update}
                    if len(json.dumps(frame).encode("utf-8")) > settings.max_output_bytes:
                        yield f"event: error\ndata: {json.dumps({'detail': 'event too large'})}\n\n"
                        return
                    yield f"data: {json.dumps(frame)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except (RunBusyError, RunTimeoutError, HTTPException) as exc:
            status = getattr(exc, "status_code", None)
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            yield f"event: error\ndata: {json.dumps({'detail': detail, 'status': status})}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
