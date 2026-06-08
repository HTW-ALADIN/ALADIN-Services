from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from openai import OpenAIError

from openai_wrapper_service.client import OpenAIWrapper, OpenAIWrapperProtocol
from openai_wrapper_service.schemas import (
    EmbeddingsRequest,
    EmbeddingsResponse,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
)

app = FastAPI(
    title="OpenAI Wrapper Service",
    description=("REST and CLI wrapper around the official OpenAI API for text generation and embeddings."),
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


@app.post(
    "/embeddings",
    response_model=EmbeddingsResponse,
    responses={502: {"model": ErrorResponse}},
    tags=["OpenAI"],
    summary="Create embeddings with the OpenAI Embeddings API",
)
def embeddings(request: EmbeddingsRequest, service: OpenAIWrapperProtocol = Depends(get_service)) -> EmbeddingsResponse:
    try:
        return service.embeddings(request)
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI API request failed: {exc}") from exc
