from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.author import AuthorProfile, AuthorQuery
from core.paper import Paper


class AuthorSearchRequest(BaseModel):
    query: AuthorQuery
    providers: list[str]
    # "authors": return matching author profiles.
    # "papers": return the papers written by the matched author(s) -- for a
    # name-only query this resolves to the best-matching author per provider
    # (ranked by citation/paper count) before fetching their papers.
    output: Literal["authors", "papers"] = "authors"
    max_results: int = Field(default=100, ge=1, le=1000)
    per_provider_max: int = Field(default=50, ge=1, le=200)
    credentials: dict[str, dict[str, str]] = Field(default_factory=dict)
    include_raw: bool = False


class AuthorProviderResultSchema(BaseModel):
    count: int
    errors: list[str] = Field(default_factory=list)


class AuthorSearchResponse(BaseModel):
    authors: list[AuthorProfile] = Field(default_factory=list)
    papers: list[Paper] = Field(default_factory=list)
    per_provider: dict[str, AuthorProviderResultSchema]
    took_ms: float
