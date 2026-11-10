"""Structured search query DSL exposed by this service's API, plus translators
into each backend's native query shape:

- scimesh: a composable `Query` AST (`title()`, `author()`, `year(lo, hi)`, ...).
- academic-mcp: a single free-text query string (its searchers do not accept a
  structured query).
"""

from __future__ import annotations

from pydantic import BaseModel
from scimesh.query.combinators import Query, author, fulltext, title, year


class YearRangeQuery(BaseModel):
    gte: int | None = None
    lte: int | None = None


class SearchQuery(BaseModel):
    text: str | None = None
    title: str | None = None
    author: str | None = None
    year: YearRangeQuery | None = None

    def to_scimesh_query(self) -> Query:
        clauses: list[Query] = []
        if self.title:
            clauses.append(title(self.title))
        if self.author:
            clauses.append(author(self.author))
        if self.text:
            clauses.append(fulltext(self.text))
        if self.year and (self.year.gte is not None or self.year.lte is not None):
            clauses.append(year(self.year.gte, self.year.lte))

        if not clauses:
            raise ValueError("SearchQuery must specify at least one of: text, title, author, year")

        combined = clauses[0]
        for clause in clauses[1:]:
            combined = combined & clause
        return combined

    def to_text_query(self) -> str:
        """Flatten to a single free-text string for academic-mcp searchers."""
        parts = [p for p in (self.title, self.text, self.author) if p]
        if not parts:
            raise ValueError("SearchQuery must specify at least one of: text, title, author, year")
        return " ".join(parts)
