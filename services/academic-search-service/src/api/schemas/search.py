from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.paper import Paper
from core.query import SearchQuery


class DedupOptions(BaseModel):
    enabled: bool = False
    strategy: Literal["auto", "strict", "aggressive"] = "auto"


class SearchRequest(BaseModel):
    query: SearchQuery
    providers: list[str]
    max_results: int = Field(default=100, ge=1, le=1000)
    per_provider_max: int = Field(default=50, ge=1, le=200)
    credentials: dict[str, dict[str, str]] = Field(default_factory=dict)
    dedup: DedupOptions = Field(default_factory=DedupOptions)
    include_raw: bool = False


class ProviderResultSchema(BaseModel):
    count: int
    errors: list[str] = Field(default_factory=list)


class DedupClusterSchema(BaseModel):
    canonical_id: str
    match_tier: str
    members: list[dict[str, str]]


class DedupReportSchema(BaseModel):
    input_count: int
    output_count: int
    duplicates_removed: int
    clusters: list[DedupClusterSchema]
    by_tier: dict[str, int]
    by_provider_pair: dict[str, int]


class SearchResponse(BaseModel):
    papers: list[Paper]
    per_provider: dict[str, ProviderResultSchema]
    dedup_report: DedupReportSchema | None = None
    took_ms: float
