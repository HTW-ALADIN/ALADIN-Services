"""Pydantic models for the text similarity service API.

Implements the discriminated union shape from the API spec §3:
- operation (top-level discriminator: similarity | retrieval | lexical_relations)
- measure/method/relation (second-level discriminator)
- backend (third-level discriminator, optional, resolves to distinct params schema)
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── Limits ────────────────────────────────────────────────────────────────────

MAX_TEXT_LENGTH = 100_000
MAX_BATCH_SIZE = 500


# ─── Similarity Measure Tags ──────────────────────────────────────────────────

SIMILARITY_MEASURES = Literal[
    "levenshtein",
    "damerau_levenshtein",
    "jaro_winkler",
    "hamming",
    "lcs",
    "token_set",
    "sequence_alignment",
    "compression_ncd",
    "phonetic",
    "tfidf_cosine",
    "embedding_cosine",
    "sbert_cosine",
    "wmd",
    "cross_encoder",
    "bertscore",
    "wordnet_similarity",
    "topic_model",
    "structural_stylistic",
]

RETRIEVAL_METHODS = Literal["fuzzy_extract", "semantic_search"]

LEXICAL_RELATIONS = Literal["synonym", "antonym", "hypernym", "hyponym"]

VALID_OPERATIONS = Literal["similarity", "retrieval", "lexical_relations"]


# ─── Request Models ───────────────────────────────────────────────────────────


class SimilarityInput(BaseModel):
    """Input for similarity operations — two texts to compare."""

    text_a: str = Field(..., max_length=MAX_TEXT_LENGTH)
    text_b: str = Field(..., max_length=MAX_TEXT_LENGTH)


class RetrievalInput(BaseModel):
    """Input for retrieval operations — query + candidates."""

    query: str = Field(..., max_length=MAX_TEXT_LENGTH)
    candidates: list[str] = Field(..., max_length=MAX_BATCH_SIZE)


class LexicalRelationsInput(BaseModel):
    """Input for lexical_relations operations — one word."""

    word: str = Field(..., max_length=MAX_TEXT_LENGTH)


class OutputConfig(BaseModel):
    """Shared output configuration for similarity operations."""

    score_type: Literal["similarity", "distance", "raw"] = "similarity"
    normalize: bool = True


class SimilarityRequest(BaseModel):
    """Request for operation: similarity."""

    operation: Literal["similarity"] = "similarity"
    measure: SIMILARITY_MEASURES
    backend: str | None = None
    input: SimilarityInput
    params: dict[str, Any] = Field(default_factory=dict)
    output: OutputConfig = Field(default_factory=OutputConfig)


class RetrievalRequest(BaseModel):
    """Request for operation: retrieval."""

    operation: Literal["retrieval"] = "retrieval"
    method: RETRIEVAL_METHODS
    backend: str | None = None
    input: RetrievalInput
    params: dict[str, Any] = Field(default_factory=dict)


class LexicalRelationsRequest(BaseModel):
    """Request for operation: lexical_relations."""

    operation: Literal["lexical_relations"] = "lexical_relations"
    relation: LEXICAL_RELATIONS
    backend: str | None = None
    input: LexicalRelationsInput
    params: dict[str, Any] = Field(default_factory=dict)


class ComputeRequest(BaseModel):
    """Discriminated union request body for POST /v1/compute.

    Uses a manual discriminator via `operation` field. At runtime,
    the handler inspects `operation` and delegates to the appropriate
    sub-model for validation.
    """

    operation: str = Field(..., description="Top-level discriminator: similarity | retrieval | lexical_relations")
    measure: str | None = Field(None, description="Required for similarity operations")
    method: str | None = Field(None, description="Required for retrieval operations")
    relation: str | None = Field(None, description="Required for lexical_relations operations")
    backend: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


# ─── Response Models ──────────────────────────────────────────────────────────


class ResultMetadata(BaseModel):
    symmetric: bool = True
    computeTimeMs: float = 0.0
    createdAt: str = ""


class ResultLinks(BaseModel):
    self: str = ""


class ResultResponse(BaseModel):
    """Result resource envelope from §3.3 of the API spec.

    The `result` field is an open dict to support both bare-scalar shapes
    (most measures) and named-fields shapes (bertscore's P/R/F1 triple).
    """

    id: str
    status: str  # pending | completed | failed
    operation: str
    measure: str
    backend: str
    input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)
    links: ResultLinks = Field(default_factory=ResultLinks, alias="_links")

    model_config = {"populate_by_name": True}


class MeasureInfo(BaseModel):
    """Entry in GET /v1/measures response."""

    operation: str
    tag: str
    backend: str
    description: str = ""
    score_direction: str = ""  # "higher_is_similar" | "lower_is_similar"
    score_range: str = ""  # e.g. "[0,1]", "[0,100]", "unbounded"
    symmetric: bool = True
    granularity: str = ""  # "char" | "token" | "word" | "sentence" | "document"
    stateful: bool = False
    async_default: bool = False


# ─── Error Models (RFC 9457) ──────────────────────────────────────────────────


class InvalidParam(BaseModel):
    name: str
    reason: str


class ProblemResponse(BaseModel):
    """RFC 9457 application/problem+json error response."""

    type: str = "about:blank"
    title: str = ""
    status: int = 400
    detail: str = ""
    invalidParams: list[InvalidParam] = Field(default_factory=list)
