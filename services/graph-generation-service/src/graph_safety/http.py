from __future__ import annotations

from threading import BoundedSemaphore

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from graph_safety.limits import LIMITS, ResourceLimitError


def problem(exc: ResourceLimitError, instance: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        media_type="application/problem+json",
        content={
            "type": "https://api.aladin.local/problems/resource-limit",
            "title": "Graph request failed",
            "status": exc.status,
            "detail": str(exc),
            "instance": instance,
            "invalidParams": [{"name": "resource", "reason": str(exc)}],
        },
    )


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.slots = BoundedSemaphore(LIMITS.concurrency * 2)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in {"/healthz", "/readyz"}:
            await self.app(scope, receive, send)
            return
        if not self.slots.acquire(blocking=False):
            await problem(ResourceLimitError("request capacity exhausted; retry later", 503), scope.get("path", ""))(
                scope, receive, send
            )
            return
        try:
            await self.receive_body(scope, receive, send)
        finally:
            self.slots.release()

    async def receive_body(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = bytearray()
        # Count actual bytes, including chunked bodies, before JSON/Pydantic decoding.
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > LIMITS.request_bytes:
                await problem(ResourceLimitError("request body exceeds the byte limit"), scope.get("path", ""))(
                    scope, receive, send
                )
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)
