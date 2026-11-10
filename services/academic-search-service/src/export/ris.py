from __future__ import annotations

from core.paper import Paper


def _entry(paper: Paper) -> str:
    lines = ["TY  - JOUR" if paper.venue else "TY  - GEN"]
    lines.append(f"TI  - {paper.title}")
    for author in paper.authors:
        lines.append(f"AU  - {author.name}")
    if paper.year:
        lines.append(f"PY  - {paper.year}")
    if paper.venue:
        lines.append(f"JO  - {paper.venue}")
    if paper.doi:
        lines.append(f"DO  - {paper.doi}")
    if paper.abstract:
        lines.append(f"AB  - {paper.abstract}")
    url = paper.landing_page_url or (paper.urls[0] if paper.urls else None)
    if url:
        lines.append(f"UR  - {url}")
    lines.append("ER  - ")
    return "\n".join(lines)


def serialize(papers: list[Paper]) -> bytes:
    return ("\n\n".join(_entry(p) for p in papers) + "\n").encode("utf-8")
