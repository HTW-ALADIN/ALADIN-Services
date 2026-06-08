from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str = Field(..., min_length=1, description="User input passed to the OpenAI Responses API.")
    model: str | None = Field(None, description="OpenAI model id. Uses the service default when omitted.")
    instructions: str | None = Field(None, description="Optional system/developer-style instructions.")
    max_output_tokens: int | None = Field(None, ge=1, le=32768)
    temperature: float | None = Field(None, ge=0, le=2)
    store: bool = Field(False, description="Whether OpenAI may store the response object.")
    metadata: dict[str, str] | None = Field(None, description="Optional metadata forwarded to OpenAI.")


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class GenerateResponse(BaseModel):
    id: str | None
    model: str
    output_text: str
    usage: TokenUsage | None = None


class EmbeddingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str | list[str] = Field(..., description="Text or batch of texts to embed.")
    model: str | None = Field(None, description="OpenAI embedding model id. Uses the service default when omitted.")
    dimensions: int | None = Field(None, ge=1, le=3072)
    user: str | None = Field(None, description="Optional end-user identifier forwarded to OpenAI.")


class EmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class EmbeddingsResponse(BaseModel):
    model: str
    data: list[EmbeddingItem]
    usage: TokenUsage | None = None


class ErrorResponse(BaseModel):
    detail: str
