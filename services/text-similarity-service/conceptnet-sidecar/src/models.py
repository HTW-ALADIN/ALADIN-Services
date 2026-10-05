"""Pydantic request/response models for the ConceptNet sidecar."""

from pydantic import BaseModel, Field

# Mirror the main service's input caps (see services/text-similarity-service/src/models.py):
# at most MAX_BATCH_SIZE pairs per request, each term at most MAX_TEXT_LENGTH chars.
MAX_BATCH_SIZE = 500
MAX_TEXT_LENGTH = 100_000


class RelatednessPair(BaseModel):
    """One word pair to score."""

    id: str = Field(..., max_length=200)
    word_a: str = Field(..., max_length=MAX_TEXT_LENGTH)
    word_b: str = Field(..., max_length=MAX_TEXT_LENGTH)
    lang: str = "en"


class RelatednessRequest(BaseModel):
    """Batch of word pairs."""

    pairs: list[RelatednessPair] = Field(default_factory=list, max_length=MAX_BATCH_SIZE)


class RelatednessItem(BaseModel):
    """One pair's result. score is None + error set for out-of-vocabulary words."""

    id: str
    score: float | None = Field(default=None)
    error: str | None = Field(default=None)
