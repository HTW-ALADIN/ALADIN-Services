"""Pydantic models for the edit distance service API."""

from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, Field, model_serializer


# ─── Shared Envelope ──────────────────────────────────────────────────────────

class InputPair(BaseModel):
    """A single input pair for text comparison."""
    id: str
    a: str
    b: str


class InputPhonetic(BaseModel):
    """A single input for phonetic encoding."""
    id: str
    text: str


# ─── Text Edit Distance - Response Models ─────────────────────────────────────

class ScalarDistanceResult(BaseModel):
    id: str
    value: float
    normalized: Optional[float] = None


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
    levenshtein: Optional[int] = None


class AlignmentResult(BaseModel):
    id: str
    edit_distance: int
    locations: Optional[list[list[Optional[int]]]] = None
    cigar: Optional[str] = None


class TextCompareResponse(BaseModel):
    algorithm: str
    backend: str
    result_type: str
    results: list[Any]
    meta: dict[str, Any] = Field(default_factory=lambda: {"compute_time_ms": 0})


# ─── Graph Edit Distance - Request Models ─────────────────────────────────────

class GraphRef(BaseModel):
    """Reference to a graph, either inline or from graph-generation service."""
    graph_ref: Optional[str] = None
    nodes: Optional[list[dict]] = None
    edges: Optional[list[dict]] = None


class GraphPair(BaseModel):
    id: str
    g1: GraphRef
    g2: GraphRef


# ─── Graph Edit Distance - Response Models ────────────────────────────────────

class GedPairResult(BaseModel):
    id: str
    upper_bound: float
    lower_bound: float
    exact: bool = False
    node_map: Optional[list[list[int]]] = None
    runtime_ms: float = 0.0

    @model_serializer
    def _clean(self) -> dict:
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
    links: dict[str, str] = Field(default_factory=dict, alias="_links")