"""Adapter wrapping `academic-mcp`'s per-source searchers behind this
service's internal adapter interface (search / download / read_fulltext).

Deliberately imports the individual `academic_mcp.sources.*Searcher` classes
directly rather than `academic_mcp.__main__.ALL_SEARCHERS`, for two reasons:

1. Importing `academic_mcp.__main__` boots a `FastMCP` server object and
   eagerly instantiates all ~18 searchers (reading credential env vars) as a
   side effect of the import itself -- unnecessary overhead/coupling for a
   library-style usage.
2. Per-request credentials (this service's design) require constructing a
   fresh, request-scoped searcher instance with an explicit `api_key`
   rather than relying on a process-wide singleton seeded from env vars.

academic-mcp's searchers do not expose a citation-graph API (only a
`citations` *count* on search results) as of the installed version, so this
adapter has no `citations()` -- citation graph expansion is scimesh-only
(see core/provider_registry.py `supports_citations`).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Protocol

from academic_mcp.sources.acm import ACMSearcher
from academic_mcp.sources.biorxiv import BioRxivSearcher
from academic_mcp.sources.core import CORESearcher
from academic_mcp.sources.crossref import CrossRefSearcher
from academic_mcp.sources.google_scholar import GoogleScholarSearcher
from academic_mcp.sources.iacr import IACRSearcher
from academic_mcp.sources.ieee import IEEESearcher
from academic_mcp.sources.jstor import JSTORSearcher
from academic_mcp.sources.medrxiv import MedRxivSearcher
from academic_mcp.sources.pmc import PMCSearcher
from academic_mcp.sources.pubmed import PubMedSearcher
from academic_mcp.sources.researchgate import ResearchGateSearcher
from academic_mcp.sources.sciencedirect import ScienceDirectSearcher
from academic_mcp.sources.springer import SpringerSearcher
from academic_mcp.sources.wos import WOSSearcher
from academic_mcp.types import Paper as AcademicMcpPaper

from core.paper import Author, Paper, compute_paper_id

logger = logging.getLogger(__name__)


class _Searcher(Protocol):
    def search(self, query: str, max_results: int = 10) -> list[AcademicMcpPaper]: ...

    def download_pdf(self, paper_id: str, save_path: str) -> str: ...

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str: ...


_NO_KEY_SEARCHERS: dict[str, type[_Searcher]] = {
    "crossref": CrossRefSearcher,
    "pubmed": PubMedSearcher,
    "pmc": PMCSearcher,
    "biorxiv": BioRxivSearcher,
    "medrxiv": MedRxivSearcher,
    "acm": ACMSearcher,
    "jstor": JSTORSearcher,
    "researchgate": ResearchGateSearcher,
    # No official API; unofficial scraper, blockable without proxies. Opt-in,
    # documented with caveats in the README (see core/provider_registry.py).
    "google_scholar": GoogleScholarSearcher,
    "iacr": IACRSearcher,
}

_API_KEY_SEARCHERS: dict[str, type[_Searcher]] = {
    "core": CORESearcher,
    "ieee": IEEESearcher,
    "springer": SpringerSearcher,
    "sciencedirect": ScienceDirectSearcher,
    "wos": WOSSearcher,
}


def _build_searcher(provider: str, credentials: dict[str, str]) -> _Searcher:
    if provider in _NO_KEY_SEARCHERS:
        return _NO_KEY_SEARCHERS[provider]()
    if provider in _API_KEY_SEARCHERS:
        return _API_KEY_SEARCHERS[provider](api_key=credentials.get("api_key"))
    raise KeyError(f"academic-mcp adapter does not handle provider '{provider}'")


def _normalize(paper: AcademicMcpPaper, provider: str) -> Paper:
    external_ids: dict[str, str] = {}
    if provider == "pubmed" and paper.paper_id:
        external_ids["pmid"] = paper.paper_id
    if provider == "crossref" and paper.doi:
        external_ids["doi"] = paper.doi

    year = None
    if paper.published_date:
        year = paper.published_date.year

    paper_id = compute_paper_id(
        doi=paper.doi or None,
        pmid=external_ids.get("pmid"),
        title=paper.title,
        year=year,
    )

    urls = [u for u in (paper.url, paper.pdf_url) if u]

    return Paper(
        id=paper_id,
        doi=paper.doi or None,
        external_ids=external_ids,
        provider=provider,
        backend="academic_mcp",
        title=paper.title,
        abstract=paper.abstract or None,
        authors=[Author(name=name) for name in (paper.authors or [])],
        year=year,
        venue=None,
        citation_count=paper.citations,
        reference_count=len(paper.references) if paper.references else None,
        open_access=False,
        pdf_url=paper.pdf_url or None,
        landing_page_url=paper.url or None,
        urls=urls,
        raw=paper.extra or None,
    )


def _search_sync(
    provider: str,
    query: str,
    credentials: dict[str, str],
    max_results: int,
) -> list[Paper]:
    searcher = _build_searcher(provider, credentials)
    raw_papers = searcher.search(query, max_results=max_results)
    return [_normalize(p, provider) for p in raw_papers]


def _download_sync(provider: str, credentials: dict[str, str], paper_id: str, dest_dir: str) -> str:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    searcher = _build_searcher(provider, credentials)
    return searcher.download_pdf(paper_id, dest_dir)


def _read_fulltext_sync(
    provider: str, credentials: dict[str, str], paper_id: str, dest_dir: str
) -> str:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    searcher = _build_searcher(provider, credentials)
    return searcher.read_paper(paper_id, dest_dir)


# All three of academic-mcp's searcher methods (`search`, `download_pdf`,
# `read_paper`) are synchronous, blocking HTTP calls under the hood. Running
# them directly on the event loop would serialize every academic-mcp-backed
# provider and freeze concurrently-running scimesh coroutines / other
# in-flight requests for the duration of each call -- defeating the
# `asyncio.gather` fan-out in core/search_service.py. `asyncio.to_thread`
# moves the blocking work off the event loop.


async def search(
    provider: str,
    query: str,
    credentials: dict[str, str],
    max_results: int,
) -> list[Paper]:
    return await asyncio.to_thread(_search_sync, provider, query, credentials, max_results)


async def download(
    provider: str,
    credentials: dict[str, str],
    paper_id: str,
    dest_dir: str,
) -> str:
    """Returns the local filesystem path of the downloaded PDF."""
    return await asyncio.to_thread(_download_sync, provider, credentials, paper_id, dest_dir)


async def read_fulltext(
    provider: str,
    credentials: dict[str, str],
    paper_id: str,
    dest_dir: str,
) -> str:
    """Returns extracted plain text (or a path, depending on the searcher)."""
    return await asyncio.to_thread(_read_fulltext_sync, provider, credentials, paper_id, dest_dir)
