from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from openai import OpenAIError

from openai_wrapper_service.client import OpenAIWrapper, OpenAIWrapperProtocol
from openai_wrapper_service.schemas import (
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
)

app = FastAPI(
    title="OpenAI Wrapper Service",
    description=("REST and CLI wrapper around the official OpenAI Responses API."),
    version="0.1.0",
)

_service = OpenAIWrapper()


def get_service() -> OpenAIWrapperProtocol:
    return _service


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={502: {"model": ErrorResponse}},
    tags=["OpenAI"],
    summary="Generate text with the OpenAI Responses API",
)
def generate(request: GenerateRequest, service: OpenAIWrapperProtocol = Depends(get_service)) -> GenerateResponse:
    try:
        return service.generate(request)
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI API request failed: {exc}") from exc
