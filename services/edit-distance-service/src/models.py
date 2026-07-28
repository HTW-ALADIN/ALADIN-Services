"""Pydantic models for the edit distance service API."""

from typing import Any

from pydantic import BaseModel, Field, model_serializer


class InputPair(BaseModel):
    """A single input pair for text comparison."""
    id: str
    a: str
    b: str


class InputPhonetic(BaseModel):
    """A single input for phonetic encoding."""
    id: str
    text: str


class ScalarDistanceResult(BaseModel):
    id: str
    value: float
    normalized: float | None = None


class SequenceResult(BaseModel):
    id: str
    value: str
    length: int


class PhoneticCodeResult(BaseModel):
    id: str
    codes: dict[str, str]


class EditScriptResult(BaseModel):
    id: str
    diffs: list[list[Any]]
    levenshtein: int | None = None


class AlignmentResult(BaseModel):
    id: str
    edit_distance: int
    locations: list[list[int | None]] | None = None
    cigar: str | None = None


class TextCompareResponse(BaseModel):
    algorithm: str
    backend: str
    result_type: str
    results: list[Any]
    meta: dict[str, Any] = Field(default_factory=lambda: {"compute_time_ms": 0})


class GraphRef(BaseModel):
    """Reference to a graph, either inline or from graph-generation service."""
    graph_ref: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None


class GraphPair(BaseModel):
    id: str
    g1: GraphRef
    g2: GraphRef


class GedPairResult(BaseModel):
    id: str
    upper_bound: float
    lower_bound: float
    exact: bool = False
    node_map: list[list[int]] | None = None
    runtime_ms: float = 0.0

    @model_serializer
    def _clean(self) -> dict:
        import math
        return {
            "id": self.id,
            "upper_bound": None if math.isinf(self.upper_bound) else self.upper_bound,
            "lower_bound": None if math.isinf(self.lower_bound) else self.lower_bound,
            "exact": self.exact,
            "node_map": self.node_map,
            "runtime_ms": self.runtime_ms,
        }


class GedResultResponse(BaseModel):
    id: str
    status: str
    algorithm: str
    backend: str
    params: dict[str, Any] = Field(default_factory=dict)
    results: list[GedPairResult]