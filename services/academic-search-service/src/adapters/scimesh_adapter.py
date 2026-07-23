"""Adapter wrapping the `scimesh` library behind this service's internal
adapter interface (search / get / citations).

Handles: arxiv, openalex, semantic_scholar, scopus (see core/provider_registry.py).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Literal

from scimesh.models import Paper as ScimeshPaper
from scimesh.providers.arxiv import Arxiv
from scimesh.providers.base import Provider as ScimeshProvider
from scimesh.providers.openalex import OpenAlex
from scimesh.providers.scopus import Scopus
from scimesh.providers.semantic_scholar import SemanticScholar
from scimesh.query.combinators import Query

from core.paper import Author, Paper, compute_paper_id

logger = logging.getLogger(__name__)

Direction = Literal["citing", "cited_by", "both"]

# scimesh's Provider.citations() uses "in"/"out"/"both"; this service's public
# API uses "citing" (backward edges, papers this one cites) / "cited_by"
# (forward edges, papers that cite this one) / "both". Map explicitly rather
# than reusing scimesh's vocabulary at the API boundary, since "in"/"out" is
# ambiguous without reading scimesh's docstring.
_DIRECTION_MAP: dict[Direction, Literal["in", "out", "both"]] = {
    "citing": "out",
    "cited_by": "in",
    "both": "both",
}


def _build_provider(provider: str, credentials: dict[str, str]) -> ScimeshProvider:
    if provider == "arxiv":
        return Arxiv()
    if provider == "openalex":
        return OpenAlex(mailto=credentials.get("mailto"))
    if provider == "semantic_scholar":
        return SemanticScholar(api_key=credentials.get("api_key"))
    if provider == "scopus":
        return Scopus(api_key=credentials.get("api_key"))
    raise KeyError(f"scimesh adapter does not handle provider '{provider}'")


def _normalize(paper: ScimeshPaper, provider: str) -> Paper:
    external_ids: dict[str, str] = {}
    if provider == "arxiv" and paper.extras.get("arxiv_id"):
        external_ids["arxiv"] = str(paper.extras["arxiv_id"])
    if provider == "semantic_scholar" and paper.extras.get("semanticScholarId"):
        external_ids["s2"] = str(paper.extras["semanticScholarId"])
    if provider == "openalex" and paper.extras.get("openalex_id"):
        external_ids["openalex"] = str(paper.extras["openalex_id"])
    if provider == "scopus" and paper.extras.get("scopus_id"):
        external_ids["scopus"] = str(paper.extras["scopus_id"])

    paper_id = compute_paper_id(
        doi=paper.doi,
        arxiv_id=external_ids.get("arxiv"),
        semantic_scholar_id=external_ids.get("s2"),
        title=paper.title,
        year=paper.year,
    )

    urls = [u for u in (paper.url, paper.pdf_url) if u]

    return Paper(
        id=paper_id,
        doi=paper.doi,
        external_ids=external_ids,
        provider=provider,
        backend="scimesh",
        title=paper.title,
        abstract=paper.abstract,
        authors=[
            Author(name=a.name, affiliations=[a.affiliation] if a.affiliation else [])
            for a in paper.authors
        ],
        year=paper.year,
        venue=paper.journal,
        citation_count=paper.citations_count,
        reference_count=paper.references_count,
        open_access=paper.open_access,
        pdf_url=paper.pdf_url,
        landing_page_url=paper.url,
        urls=urls,
        raw=dict(paper.extras) if paper.extras else None,
    )


async def search(
    provider: str,
    query: Query,
    credentials: dict[str, str],
    max_results: int,
) -> list[Paper]:
    scimesh_provider = _build_provider(provider, credentials)
    papers: list[Paper] = []
    async with scimesh_provider:
        count = 0
        async for raw_paper in scimesh_provider.search(query):
            papers.append(_normalize(raw_paper, provider))
            count += 1
            if count >= max_results:
                break
    return papers


async def get(provider: str, credentials: dict[str, str], paper_id: str) -> Paper | None:
    scimesh_provider = _build_provider(provider, credentials)
    async with scimesh_provider:
        raw_paper = await scimesh_provider.get(paper_id)
    if raw_paper is None:
        return None
    return _normalize(raw_paper, provider)


async def citations(
    provider: str,
    credentials: dict[str, str],
    paper_id: str,
    direction: Direction,
    max_results: int,
) -> list[Paper]:
    scimesh_provider = _build_provider(provider, credentials)
    scimesh_direction = _DIRECTION_MAP[direction]
    papers: list[Paper] = []
    async with scimesh_provider:
        stream: AsyncIterator[ScimeshPaper] = scimesh_provider.citations(
            paper_id, direction=scimesh_direction, max_results=max_results
        )
        async for raw_paper in stream:
            papers.append(_normalize(raw_paper, provider))
    return papers
