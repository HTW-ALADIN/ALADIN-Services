"""Pydantic models for the edit distance service API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


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


# ─── Text Edit Distance - Request Models ──────────────────────────────────────

class TextCompareRequest(BaseModel):
    """Base model for text comparison requests. Each algorithm variant has its own schema."""
    algorithm: str
    backend: Optional[str] = None
    inputs: list[InputPair] = Field(..., min_length=1)


class LevenshteinParams(BaseModel):
    weights: Optional[tuple[int, int, int]] = None
    processor: Optional[Any] = None
    score_cutoff: Optional[float] = None
    qval: Optional[int] = None  # textdistance
    pad: Optional[bool] = None  # Hamming


class LevenshteinRequest(TextCompareRequest):
    algorithm: Literal["levenshtein"] = "levenshtein"
    backend: Literal["rapidfuzz", "textdistance", "jellyfish", "edlib"] = "rapidfuzz"
    params: LevenshteinParams = Field(default_factory=LevenshteinParams)


class DamerauLevenshteinParams(BaseModel):
    processor: Optional[Any] = None
    score_cutoff: Optional[float] = None
    qval: Optional[int] = None


class DamerauLevenshteinRequest(TextCompareRequest):
    algorithm: Literal["damerau_levenshtein"] = "damerau_levenshtein"
    backend: Literal["rapidfuzz", "textdistance", "jellyfish"] = "rapidfuzz"
    params: DamerauLevenshteinParams = Field(default_factory=DamerauLevenshteinParams)


class HammingParams(BaseModel):
    pad: Optional[bool] = None
    processor: Optional[Any] = None
    score_cutoff: Optional[float] = None
    qval: Optional[int] = None


class HammingRequest(TextCompareRequest):
    algorithm: Literal["hamming"] = "hamming"
    backend: Literal["rapidfuzz", "textdistance", "jellyfish"] = "rapidfuzz"
    params: HammingParams = Field(default_factory=HammingParams)


class JaroWinklerParams(BaseModel):
    prefix_weight: Optional[float] = None
    winklerize: Optional[bool] = None
    long_tolerance: Optional[bool] = None
    variant: Literal["jaro", "jaro_winkler"] = "jaro_winkler"


class JaroWinklerRequest(TextCompareRequest):
    algorithm: Literal["jaro_winkler"] = "jaro_winkler"
    backend: Literal["rapidfuzz", "textdistance", "jellyfish"] = "rapidfuzz"
    params: JaroWinklerParams = Field(default_factory=JaroWinklerParams)


class OsaParams(BaseModel):
    processor: Optional[Any] = None
    score_cutoff: Optional[float] = None


class OsaRequest(TextCompareRequest):
    algorithm: Literal["osa"] = "osa"
    backend: Literal["rapidfuzz"] = "rapidfuzz"
    params: OsaParams = Field(default_factory=OsaParams)


class IndelParams(BaseModel):
    processor: Optional[Any] = None
    score_cutoff: Optional[float] = None
    qval: Optional[int] = None


class IndelRequest(TextCompareRequest):
    algorithm: Literal["indel"] = "indel"
    backend: Literal["rapidfuzz", "textdistance"] = "rapidfuzz"
    params: IndelParams = Field(default_factory=IndelParams)


class LcsRequest(TextCompareRequest):
    algorithm: Literal["lcs"] = "lcs"
    backend: Literal["textdistance"] = "textdistance"
    params: dict = Field(default_factory=dict)


class NeedlemanWunschParams(BaseModel):
    gap_cost: float = 1.0
    sim_func: Optional[str] = None  # 'exact' | 'hamming'


class NeedlemanWunschRequest(TextCompareRequest):
    algorithm: Literal["needleman_wunsch"] = "needleman_wunsch"
    backend: Literal["textdistance"] = "textdistance"
    params: NeedlemanWunschParams = Field(default_factory=NeedlemanWunschParams)


class GotohRequest(TextCompareRequest):
    algorithm: Literal["gotoh"] = "gotoh"
    backend: Literal["textdistance"] = "textdistance"
    params: dict = Field(default_factory=dict)


class SmithWatermanRequest(TextCompareRequest):
    algorithm: Literal["smith_waterman"] = "smith_waterman"
    backend: Literal["textdistance"] = "textdistance"
    params: dict = Field(default_factory=dict)


class TokenSetSimilarityParams(BaseModel):
    metric: Literal["jaccard", "sorensen", "tversky", "cosine"] = "jaccard"
    qval: Optional[int] = None


class TokenSetSimilarityRequest(TextCompareRequest):
    algorithm: Literal["token_set_similarity"] = "token_set_similarity"
    backend: Literal["textdistance"] = "textdistance"
    params: TokenSetSimilarityParams = Field(default_factory=TokenSetSimilarityParams)


class NcdParams(BaseModel):
    qval: int = 1
    compressor: str = "zlib"  # 'zlib' | 'bzip2' | 'lzma'


class NcdRequest(TextCompareRequest):
    algorithm: Literal["ncd"] = "ncd"
    backend: Literal["textdistance"] = "textdistance"
    params: NcdParams = Field(default_factory=NcdParams)


class PhoneticEncodingParams(BaseModel):
    scheme: Literal["soundex", "metaphone", "nysiis", "match_rating"] = "soundex"


class PhoneticEncodingRequest(BaseModel):
    algorithm: Literal["phonetic_encoding"] = "phonetic_encoding"
    backend: Literal["jellyfish"] = "jellyfish"
    params: PhoneticEncodingParams = Field(default_factory=PhoneticEncodingParams)
    inputs: list[InputPhonetic] = Field(..., min_length=1)


class LongSequenceAlignmentParams(BaseModel):
    mode: Literal["NW", "SHW", "HW"] = "NW"
    task: Literal["distance", "path", "locations"] = "distance"
    k: Optional[int] = None
    additional_equalites: Optional[list[tuple[str, str]]] = None


class LongSequenceAlignmentRequest(TextCompareRequest):
    algorithm: Literal["long_sequence_alignment"] = "long_sequence_alignment"
    backend: Literal["edlib"] = "edlib"
    params: LongSequenceAlignmentParams = Field(default_factory=LongSequenceAlignmentParams)


class DiffPatchRequest(TextCompareRequest):
    algorithm: Literal["diff_patch"] = "diff_patch"
    backend: Literal["diff_match_patch"] = "diff_match_patch"
    params: dict = Field(default_factory=dict)


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


class EditCosts(BaseModel):
    node_ins: float = 1.0
    node_del: float = 1.0
    node_subst: float = 1.0
    edge_ins: float = 1.0
    edge_del: float = 1.0
    edge_subst: float = 1.0


class GedOutput(BaseModel):
    include_node_map: bool = False


class GedAStarParams(BaseModel):
    mode: Literal["exact", "anytime", "path"] = "exact"
    node_subst_cost: Optional[float] = None
    node_del_cost: Optional[float] = None
    node_ins_cost: Optional[float] = None
    edge_subst_cost: Optional[float] = None
    edge_del_cost: Optional[float] = None
    edge_ins_cost: Optional[float] = None
    upper_bound: Optional[float] = None
    timeout_ms: Optional[int] = None
    method: Optional[str] = None  # GEDLIB: F2, BLP_NO_EDGE_LABELS
    edit_cost_model: Optional[str] = None  # GEDLIB: CHEM_1, etc.


class GedAStarRequest(BaseModel):
    algorithm: Literal["ged_astar"] = "ged_astar"
    backend: Literal["networkx", "gedlib"] = "networkx"
    params: GedAStarParams = Field(default_factory=GedAStarParams)
    graphs: list[GraphPair] = Field(..., min_length=1)
    output: GedOutput = Field(default_factory=GedOutput)


class GedHeuristicParams(BaseModel):
    method: Literal[
        "BIPARTITE", "IPFP", "REFINE",
        "ANCHOR_AWARE_GED", "BRANCH", "NODE", "RING", "SUBGRAPH", "WALKS"
    ] = "BIPARTITE"
    edit_costs: EditCosts = Field(default_factory=EditCosts)
    timeout_ms: Optional[int] = None


class GedHeuristicRequest(BaseModel):
    algorithm: Literal["ged_heuristic"] = "ged_heuristic"
    backend: Literal["gedlib", "gmatch4py"] = "gedlib"
    params: GedHeuristicParams = Field(default_factory=GedHeuristicParams)
    graphs: list[GraphPair] = Field(..., min_length=1)
    output: GedOutput = Field(default_factory=GedOutput)


class GedHausdorffParams(BaseModel):
    node_del: float = 1.0
    node_ins: float = 1.0
    edge_del: float = 1.0
    edge_ins: float = 1.0


class GedHausdorffRequest(BaseModel):
    algorithm: Literal["ged_hausdorff"] = "ged_hausdorff"
    backend: Literal["gmatch4py"] = "gmatch4py"
    params: GedHausdorffParams = Field(default_factory=GedHausdorffParams)
    graphs: list[GraphPair] = Field(..., min_length=1)


class GedGreedyParams(BaseModel):
    node_del: float = 1.0
    node_ins: float = 1.0
    edge_del: float = 1.0
    edge_ins: float = 1.0


class GedGreedyRequest(BaseModel):
    algorithm: Literal["ged_greedy"] = "ged_greedy"
    backend: Literal["gmatch4py"] = "gmatch4py"
    params: GedGreedyParams = Field(default_factory=GedGreedyParams)
    graphs: list[GraphPair] = Field(..., min_length=1)


# ─── Graph Edit Distance - Response Models ────────────────────────────────────

class GedPairResult(BaseModel):
    id: str
    upper_bound: float
    lower_bound: float
    exact: bool = False
    node_map: Optional[list[list[int]]] = None
    runtime_ms: float = 0.0


class GedResultResponse(BaseModel):
    id: str
    status: str
    algorithm: str
    backend: str
    params: dict[str, Any] = Field(default_factory=dict)
    results: list[GedPairResult]
    links: dict[str, str] = Field(default_factory=dict, alias="_links")


# ─── Algorithm Discovery ──────────────────────────────────────────────────────

class AlgorithmEntry(BaseModel):
    algorithm: str
    backend: str
    families: list[str] = Field(default_factory=list)
    result_type: str = "scalar_distance"
    description: str = ""