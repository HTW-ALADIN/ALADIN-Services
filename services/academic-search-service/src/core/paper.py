"""Canonical Paper schema shared by every backend adapter, the dedup engine,
the export serializers, and the citation graph builder.

Every backend-specific result (scimesh's ``models.Paper`` dataclass,
academic-mcp's ``types.Paper`` dataclass) is normalized into this single shape
before it leaves the adapter layer.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    affiliations: list[str] = Field(default_factory=list)
    orcid: str | None = None


class Paper(BaseModel):
    id: str
    doi: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    provider: str
    backend: str

    title: str
    abstract: str | None = None
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None

    citation_count: int | None = None
    reference_count: int | None = None

    open_access: bool = False
    pdf_url: str | None = None
    landing_page_url: str | None = None
    urls: list[str] = Field(default_factory=list)

    raw: dict[str, Any] | None = None

    # Populated only in citation-graph responses.
    depth: int | None = None
    is_seed: bool | None = None

    # Populated only when this Paper is the canonical representative of a
    # dedup cluster (see dedup/engine.py).
    merged_from: list[str] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace for fuzzy-matching comparisons."""
    return _NON_ALNUM.sub(" ", title.lower()).strip()


def compute_paper_id(
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    pmid: str | None = None,
    semantic_scholar_id: str | None = None,
    title: str,
    year: int | None,
) -> str:
    """Identifier-priority chain: DOI -> arXiv ID -> PMID -> S2 ID -> title+year hash.

    This is the single source of truth for "is this the same paper" used by both
    the Normalizer (to assign `Paper.id`) and the Dedup Engine's exact-match tier.
    """
    if doi:
        basis = f"doi:{doi.strip().lower()}"
    elif arxiv_id:
        basis = f"arxiv:{arxiv_id.strip().lower()}"
    elif pmid:
        basis = f"pmid:{pmid.strip().lower()}"
    elif semantic_scholar_id:
        basis = f"s2:{semantic_scholar_id.strip().lower()}"
    else:
        basis = f"title_year:{normalize_title(title)}:{year or ''}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
