"""Pydantic models for the edit distance service API."""

from typing import Any

from pydantic import BaseModel, Field, model_serializer

# ─── Input Models (must precede request models that reference them) ──────────


class InputPair(BaseModel):
    id: str
    a: str
    b: str


class InputPhonetic(BaseModel):
    id: str
    text: str


class GraphRef(BaseModel):
    """Graph representation supporting multiple input formats.

    Default format (no ``format`` field): nodes + edges with attrs.
    ``format=\"node_link\"``: networkx JSON node-link format (requires nodes+links).
    ``format=\"adjacency_matrix\"``: dense matrix (requires matrix+optional node_labels).
    """

    # Default format: explicit nodes + edges
    nodes: list[dict] | None = None
    edges: list[dict] | None = None

    # Alternative format selector
    format: str | None = Field(
        None,
        description="Graph format: 'node_link' (networkx), 'adjacency_matrix', or omit for nodes+edges",
    )

    # node_link format fields
    links: list[dict] | None = None
    directed: bool = False

    # adjacency_matrix format fields
    matrix: list[list[float]] | None = None
    node_labels: list[str] | None = None


class GraphPair(BaseModel):
    id: str
    g1: GraphRef
    g2: GraphRef


# ─── Request Models ───────────────────────────────────────────────────────────


class TextCompareRequest(BaseModel):
    """Request body for /v1/text/distance."""

    algorithm: str
    backend: str | None = None  # None = use default
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: list[InputPair | InputPhonetic]


class GedComputeRequest(BaseModel):
    algorithm: str
    backend: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    graphs: list[GraphPair]


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
    diffs: list[list[int | str]]
    levenshtein: int | None = None


class AlignmentResult(BaseModel):
    id: str
    edit_distance: int
    locations: list[list[int | None]] | None = None
    cigar: str | None = None


ResultModel = (
    ScalarDistanceResult
    | SequenceResult
    | PhoneticCodeResult
    | EditScriptResult
    | AlignmentResult
)


class TextCompareResponse(BaseModel):
    algorithm: str
    backend: str
    result_type: str
    results: list[ResultModel]
    meta: dict[str, Any] = Field(default_factory=lambda: {"compute_time_ms": 0})


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
    algorithm: str
    backend: str
    params: dict[str, Any] = Field(default_factory=dict)
    results: list[GedPairResult]
