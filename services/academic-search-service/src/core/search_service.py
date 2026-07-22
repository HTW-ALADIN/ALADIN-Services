"""Search orchestrator: fans out a structured query across the requested
providers in parallel, isolating per-provider failures, then optionally runs
the Dedup Engine over the merged result set.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from adapters import academic_mcp_adapter, scimesh_adapter
from config import settings
from core.credentials import resolve_credentials
from core.paper import Paper
from core.provider_registry import get_provider_spec
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
    try:
        spec = get_provider_spec(provider)
    except KeyError:
        return provider, [], ["unknown_provider"]

    resolution = resolve_credentials(provider, credentials.get(provider))
    if not resolution.ok:
        return provider, [], resolution.errors

    try:
        if spec.backend == "scimesh":
            coro = scimesh_adapter.search(
                provider, query.to_scimesh_query(), resolution.credentials, per_provider_max
            )
        else:
            coro = academic_mcp_adapter.search(
                provider, query.to_text_query(), resolution.credentials, per_provider_max
            )
        # A single hung/slow provider must not block the whole request
        # indefinitely -- bound each provider call and report a timeout as a
        # per-provider error, same as any other provider failure.
        papers = await asyncio.wait_for(coro, timeout=settings.provider_timeout_seconds)
        return provider, papers, []
    except TimeoutError:
        return provider, [], [f"provider_timeout: exceeded {settings.provider_timeout_seconds}s"]
    except Exception as exc:  # noqa: BLE001 - one provider's failure must not fail the request
        return provider, [], [f"provider_error: {exc}"]


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
