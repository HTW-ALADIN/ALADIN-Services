"""Pydantic models for the text similarity service API.

Mirrors the edit-distance-service request/response style: a flat, synchronous
API where every compute endpoint takes ``algorithm`` + optional ``backend``
(the default backend is auto-selected), ``params`` and a batch ``inputs`` list.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

# ─── Limits ────────────────────────────────────────────────────────────────────
MAX_TEXT_LENGTH = 100_000
MAX_BATCH_SIZE = 500


# ─── Input Models ──────────────────────────────────────────────────────────────


class SimilarityInput(BaseModel):
    """One text pair for POST /v1/text/distance."""

    id: str
    a: str = Field(..., max_length=MAX_TEXT_LENGTH)
    b: str = Field(..., max_length=MAX_TEXT_LENGTH)


class RetrievalInput(BaseModel):
    """One query + candidate list for POST /v1/text/retrieval."""

    id: str
    query: str = Field(..., max_length=MAX_TEXT_LENGTH)
    candidates: list[str] = Field(..., max_length=MAX_BATCH_SIZE)

    @field_validator("candidates")
    @classmethod
    def _limit_candidates(cls, v: list[str]) -> list[str]:
        for cand in v:
            if len(cand) > MAX_TEXT_LENGTH:
                raise ValueError(f"each candidate must be at most {MAX_TEXT_LENGTH} characters")
        total = sum(len(cand) for cand in v)
        if total > MAX_TEXT_LENGTH:
            raise ValueError(f"total candidate length per input must be at most {MAX_TEXT_LENGTH} characters")
        return v


class LexicalInput(BaseModel):
    """One word for POST /v1/text/lexical."""

    id: str
    word: str = Field(..., max_length=MAX_TEXT_LENGTH)


# ─── Request Models ────────────────────────────────────────────────────────────


class TextDistanceRequest(BaseModel):
    """Request body for POST /v1/text/distance."""

    algorithm: str
    backend: str | None = None  # None = auto-select the default backend
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: list[SimilarityInput] = Field(..., max_length=MAX_BATCH_SIZE)


class RetrievalRequest(BaseModel):
    """Request body for POST /v1/text/retrieval."""

    algorithm: str
    backend: str | None = None  # None = auto-select the default backend
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: list[RetrievalInput] = Field(..., max_length=MAX_BATCH_SIZE)


class LexicalRequest(BaseModel):
    """Request body for POST /v1/text/lexical."""

    algorithm: str
    backend: str | None = None  # None = auto-select the default backend
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: list[LexicalInput] = Field(..., max_length=MAX_BATCH_SIZE)


# ─── Response Models ───────────────────────────────────────────────────────────


class TextResult(BaseModel):
    """One computation result, keyed by the caller-supplied input id."""

    id: str
    result: dict[str, Any] = Field(default_factory=dict)


class TextComputeResponse(BaseModel):
    """Response for every POST /v1/text/* endpoint."""

    algorithm: str
    backend: str
    results: list[TextResult]
    meta: dict[str, Any] = Field(default_factory=lambda: {"compute_time_ms": 0})
