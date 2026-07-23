from __future__ import annotations

import csv as csv_module
import io

from core.paper import Paper

_COLUMNS = [
    "id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "provider",
    "citation_count",
    "open_access",
    "pdf_url",
    "landing_page_url",
]


def _row(paper: Paper) -> dict[str, str]:
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": "; ".join(a.name for a in paper.authors),
        "year": str(paper.year or ""),
        "venue": paper.venue or "",
        "doi": paper.doi or "",
        "provider": paper.provider,
        "citation_count": str(paper.citation_count or ""),
        "open_access": str(paper.open_access),
        "pdf_url": paper.pdf_url or "",
        "landing_page_url": paper.landing_page_url or "",
    }


def serialize(papers: list[Paper]) -> bytes:
    buffer = io.StringIO()
    writer = csv_module.DictWriter(buffer, fieldnames=_COLUMNS)
    writer.writeheader()
    for paper in papers:
        writer.writerow(_row(paper))
    return buffer.getvalue().encode("utf-8")
