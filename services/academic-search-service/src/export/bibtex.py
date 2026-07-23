from __future__ import annotations

import re

from core.paper import Paper

_KEY_SAFE = re.compile(r"[^A-Za-z0-9]+")


def _cite_key(paper: Paper) -> str:
    first_author = paper.authors[0].name.split()[-1] if paper.authors else "anon"
    year = paper.year or "n_d"
    base = f"{first_author}{year}"
    return _KEY_SAFE.sub("", base) or "entry"


def _entry_type(paper: Paper) -> str:
    if paper.venue:
        return "article"
    return "misc"


def _escape(value: str) -> str:
    return value.replace("{", "\\{").replace("}", "\\}")


def _entry(paper: Paper) -> str:
    fields: dict[str, str] = {"title": _escape(paper.title)}
    if paper.authors:
        fields["author"] = " and ".join(a.name for a in paper.authors)
    if paper.year:
        fields["year"] = str(paper.year)
    if paper.venue:
        fields["journal"] = _escape(paper.venue)
    if paper.doi:
        fields["doi"] = paper.doi
    if paper.abstract:
        fields["abstract"] = _escape(paper.abstract)
    if paper.landing_page_url or paper.urls:
        fields["url"] = paper.landing_page_url or paper.urls[0]

    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items())
    return f"@{_entry_type(paper)}{{{_cite_key(paper)},\n{body}\n}}"


def serialize(papers: list[Paper]) -> bytes:
    return ("\n\n".join(_entry(p) for p in papers) + "\n").encode("utf-8")
