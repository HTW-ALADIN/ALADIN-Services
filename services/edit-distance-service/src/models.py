"""Pydantic models for the edit distance service API."""

from typing import Any

from pydantic import BaseModel, Field, model_serializer, model_validator

# ─── Limits ────────────────────────────────────────────────────────────────────
# Several algorithms are O(n*m) or worse (textdistance pure-Python DP, NCD
# compressors, Needleman-Wunsch/Gotoh/Smith-Waterman alignment) or exponential
# (exact graph edit distance). These caps bound worst-case CPU/memory per
# request; they are generous for real workloads while preventing a single
# request (or malicious input) from exhausting resources for all callers.
MAX_TEXT_LENGTH = 100_000
MAX_BATCH_SIZE = 500
MAX_GRAPH_NODES = 200
MAX_GRAPH_EDGES = 2_000

# ─── Input Models (must precede request models that reference them) ──────────


class InputPair(BaseModel):
    id: str
    a: str = Field(..., max_length=MAX_TEXT_LENGTH)
    b: str = Field(..., max_length=MAX_TEXT_LENGTH)


class InputPhonetic(BaseModel):
    id: str
    text: str = Field(..., max_length=MAX_TEXT_LENGTH)


class GraphRef(BaseModel):
    """Graph representation supporting multiple input formats.

    Default format (no ``format`` field): nodes + edges with attrs.
    ``format=\"node_link\"``: networkx JSON node-link format (requires nodes+links).
    ``format=\"adjacency_matrix\"``: dense matrix (requires matrix+optional node_labels).
    """

    # Default format: explicit nodes + edges
    nodes: list[dict] | None = Field(None, max_length=MAX_GRAPH_NODES)
    edges: list[dict] | None = Field(None, max_length=MAX_GRAPH_EDGES)

    # Alternative format selector
    format: str | None = Field(
        None,
        description="Graph format: 'node_link' (networkx), 'adjacency_matrix', or omit for nodes+edges",
    )

    # node_link format fields
    links: list[dict] | None = Field(None, max_length=MAX_GRAPH_EDGES)
    directed: bool = False

    # adjacency_matrix format fields
    matrix: list[list[float]] | None = Field(None, max_length=MAX_GRAPH_NODES)
    node_labels: list[str] | None = Field(None, max_length=MAX_GRAPH_NODES)

    @model_validator(mode="after")
    def _validate_matrix_row_length(self) -> "GraphRef":
        # Field(max_length=...) only bounds the outer list (row count); it
        # does not recurse into nested lists, so each row's length must be
        # checked explicitly or the adjacency_matrix format has no effective
        # size cap at all.
        if self.matrix is not None:
            for row in self.matrix:
                if len(row) > MAX_GRAPH_NODES:
                    raise ValueError(
                        f"adjacency matrix row exceeds max length of {MAX_GRAPH_NODES}"
                    )
        return self


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
    inputs: list[InputPair | InputPhonetic] = Field(..., max_length=MAX_BATCH_SIZE)


class GedComputeRequest(BaseModel):
    algorithm: str
    backend: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    graphs: list[GraphPair] = Field(..., max_length=MAX_BATCH_SIZE)


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
    # Node IDs are whatever the caller supplied (e.g. string labels in the
    # default/adjacency_matrix formats), not necessarily integers.
    node_map: list[list[Any]] | None = None
    runtime_ms: float = 0.0
    error: str | None = None

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
            "error": self.error,
        }


class GedResultResponse(BaseModel):
    id: str
    algorithm: str
    backend: str
    params: dict[str, Any] = Field(default_factory=dict)
    results: list[GedPairResult]
