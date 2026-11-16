from fastapi import HTTPException, Request
from starlette.types import Message


class RequestBodyTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413)


def limit_request_body(request: Request, max_bytes: int) -> Request:
    received_bytes = 0
    original_receive = request.receive

    async def receive() -> Message:
        nonlocal received_bytes
        message = await original_receive()
        if message["type"] == "http.request":
            received_bytes += len(message.get("body", b""))
            if received_bytes > max_bytes:
                raise RequestBodyTooLarge()
        return message

    return Request(request.scope, receive)
