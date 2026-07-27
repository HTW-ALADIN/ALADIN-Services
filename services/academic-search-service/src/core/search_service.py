"""Search orchestrator: fans out a structured query across the requested
providers in parallel, isolating per-provider failures, then optionally runs
the Dedup Engine over the merged result set.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from adapters import academic_mcp_adapter, scimesh_adapter
from core.paper import Paper
from core.provider_fanout import run_provider
from core.query import SearchQuery
from dedup.engine import DedupReport, Strategy, deduplicate


@dataclass
class ProviderOutcome:
    count: int
    errors: list[str] = field(default_factory=list)


@dataclass
class SearchOutcome:
    papers: list[Paper]
    per_provider: dict[str, ProviderOutcome]
    dedup_report: DedupReport | None
    took_ms: float


async def _search_one_provider(
    provider: str,
    query: SearchQuery,
    credentials: dict[str, dict[str, str]],
    per_provider_max: int,
) -> tuple[str, list[Paper], list[str]]:
    async def build_coro(spec, creds: dict[str, str]) -> list[Paper]:
        if spec.backend == "scimesh":
            return await scimesh_adapter.search(
                provider, query.to_scimesh_query(), creds, per_provider_max
            )
        return await academic_mcp_adapter.search(
            provider, query.to_text_query(), creds, per_provider_max
        )

    papers, errors = await run_provider(provider, credentials, build_coro, [])
    return provider, papers, errors


async def run_search(
    query: SearchQuery,
    providers: list[str],
    credentials: dict[str, dict[str, str]] | None,
    max_results: int,
    per_provider_max: int,
    dedup_enabled: bool,
    dedup_strategy: Strategy,
    include_raw: bool,
) -> SearchOutcome:
    start = time.monotonic()
    credentials = credentials or {}

    results = await asyncio.gather(
        *[_search_one_provider(p, query, credentials, per_provider_max) for p in providers]
    )

    all_papers: list[Paper] = []
    per_provider: dict[str, ProviderOutcome] = {}
    for provider, papers, errors in results:
        per_provider[provider] = ProviderOutcome(count=len(papers), errors=errors)
        all_papers.extend(papers)

    if len(all_papers) > max_results:
        all_papers = all_papers[:max_results]

    if not include_raw:
        all_papers = [p.model_copy(update={"raw": None}) for p in all_papers]

    dedup_report: DedupReport | None = None
    if dedup_enabled:
        # deduplicate() is CPU-bound (O(n^2) fuzzy title comparisons in the
        # worst case); run it off the event loop so it can't stall other
        # concurrent requests.
        all_papers, dedup_report = await asyncio.to_thread(deduplicate, all_papers, dedup_strategy)

    took_ms = (time.monotonic() - start) * 1000
    return SearchOutcome(
        papers=all_papers,
        per_provider=per_provider,
        dedup_report=dedup_report,
        took_ms=took_ms,
    )
