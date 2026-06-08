from __future__ import annotations

from typing import Protocol

from openai import OpenAI

from openai_wrapper_service.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RESPONSE_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
)
from openai_wrapper_service.schemas import (
    EmbeddingItem,
    EmbeddingsRequest,
    EmbeddingsResponse,
    GenerateRequest,
    GenerateResponse,
    TokenUsage,
)


class OpenAIWrapperProtocol(Protocol):
    def generate(self, request: GenerateRequest) -> GenerateResponse: ...

    def embeddings(self, request: EmbeddingsRequest) -> EmbeddingsResponse: ...


class OpenAIWrapper:
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        model = request.model or DEFAULT_RESPONSE_MODEL
        payload = {
            "model": model,
            "input": request.input,
            "store": request.store,
        }
        if request.instructions is not None:
            payload["instructions"] = request.instructions
        if request.max_output_tokens is not None:
            payload["max_output_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.metadata is not None:
            payload["metadata"] = request.metadata

        response = self._get_client().responses.create(**payload)
        return GenerateResponse(
            id=getattr(response, "id", None),
            model=getattr(response, "model", model),
            output_text=getattr(response, "output_text", ""),
            usage=_usage_from_response(response),
        )

    def embeddings(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        model = request.model or DEFAULT_EMBEDDING_MODEL
        payload = {
            "model": model,
            "input": request.input,
        }
        if request.dimensions is not None:
            payload["dimensions"] = request.dimensions
        if request.user is not None:
            payload["user"] = request.user

        response = self._get_client().embeddings.create(**payload)
        data = [
            EmbeddingItem(index=getattr(item, "index", index), embedding=list(getattr(item, "embedding")))
            for index, item in enumerate(response.data)
        ]
        return EmbeddingsResponse(
            model=getattr(response, "model", model),
            data=data,
            usage=_usage_from_response(response),
        )

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(timeout=DEFAULT_TIMEOUT_SECONDS)
        return self._client


def _usage_from_response(response: object) -> TokenUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    input_tokens = getattr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", None)

    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)
