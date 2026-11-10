"""Author search orchestrator: fans out a name/ID author lookup across the
requested providers, isolating per-provider failures, and returns either
author profiles or the papers authored by the matched author(s) -- mirrors
core/search_service.py's shape and error-isolation semantics.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal

from adapters import author_adapter
from core.author import AuthorProfile, AuthorQuery
from core.paper import Paper
from core.provider_fanout import run_provider
from core.provider_registry import get_provider_spec

Output = Literal["authors", "papers"]


@dataclass
class AuthorProviderOutcome:
    count: int
    errors: list[str] = field(default_factory=list)


@dataclass
class AuthorSearchOutcome:
    authors: list[AuthorProfile]
    papers: list[Paper]
    per_provider: dict[str, AuthorProviderOutcome]
    took_ms: float


async def _search_one_provider(
    provider: str,
    query: AuthorQuery,
    output: Output,
    credentials: dict[str, dict[str, str]],
    per_provider_max: int,
) -> tuple[str, list[AuthorProfile], list[Paper], list[str]]:
    # run_provider() only knows about ProviderSpec/credentials, not this
    # feature's author-search-specific gating -- check that here before
    # handing off, same isolation guarantee (an unsupported provider is
    # reported per-provider, not a request failure).
    try:
        spec = get_provider_spec(provider)
    except KeyError:
        return provider, [], [], ["unknown_provider"]
    if not spec.supports_author_search:
        return provider, [], [], ["author_search_not_supported"]

    async def build_coro(_spec, creds: dict[str, str]):
        if output == "authors":
            return await author_adapter.search_authors(provider, query, creds, per_provider_max)
        return await author_adapter.papers_by_author(provider, query, creds, per_provider_max)

    result, errors = await run_provider(provider, credentials, build_coro, [])
    if errors:
        return provider, [], [], errors
    if output == "authors":
        return provider, result, [], []
    return provider, [], result, []


async def run_author_search(
    query: AuthorQuery,
    providers: list[str],
    output: Output,
    credentials: dict[str, dict[str, str]] | None,
    max_results: int,
    per_provider_max: int,
    include_raw: bool,
) -> AuthorSearchOutcome:
    # AuthorQuery already validates has_criteria() at construction time (see
    # core/author.py's model_validator); this is a defensive re-check for any
    # AuthorQuery built programmatically (e.g. from tests) rather than via the
    # API request model.
    if not query.has_criteria():
        raise ValueError("AuthorQuery must specify a name and/or at least one id")

    start = time.monotonic()
    credentials = credentials or {}

    results = await asyncio.gather(
        *[_search_one_provider(p, query, output, credentials, per_provider_max) for p in providers]
    )

    all_authors: list[AuthorProfile] = []
    all_papers: list[Paper] = []
    per_provider: dict[str, AuthorProviderOutcome] = {}
    for provider, authors, papers, errors in results:
        per_provider[provider] = AuthorProviderOutcome(
            count=len(authors) + len(papers), errors=errors
        )
        all_authors.extend(authors)
        all_papers.extend(papers)

    if len(all_authors) > max_results:
        all_authors = all_authors[:max_results]
    if len(all_papers) > max_results:
        all_papers = all_papers[:max_results]

    if not include_raw:
        all_authors = [a.model_copy(update={"raw": None}) for a in all_authors]
        all_papers = [p.model_copy(update={"raw": None}) for p in all_papers]

    took_ms = (time.monotonic() - start) * 1000
    return AuthorSearchOutcome(
        authors=all_authors,
        papers=all_papers,
        per_provider=per_provider,
        took_ms=took_ms,
    )
