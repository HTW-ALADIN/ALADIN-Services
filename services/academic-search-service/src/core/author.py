"""Author search domain model.

`Paper.authors` (see core/paper.py) only ever carries a bare name (plus,
rarely, an affiliation/ORCID) as embedded in a paper record -- there was
previously no way to search *for* an author directly, by name or by any of
the author identifier schemes the already-integrated provider databases
expose. This module defines the request/response shapes for that lookup:

- `AuthorIdentifier`: the "sensible selection" of author ID schemes available
  from providers this service already talks to -- ORCID (cross-provider,
  https://orcid.org), OpenAlex author ID (`A...`), Semantic Scholar author ID,
  and Scopus/Elsevier author ID. See `core/provider_registry.py`'s
  `author_id_fields` for which provider(s) can resolve which field directly.
- `AuthorQuery`: name and/or one or more of the above identifiers.
- `AuthorProfile`: a normalized author record returned when the caller asks
  for author profiles rather than papers (see core/author_search_service.py).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class AuthorIdentifier(BaseModel):
    orcid: str | None = None
    openalex_author_id: str | None = None
    semantic_scholar_author_id: str | None = None
    scopus_author_id: str | None = None

    def is_empty(self) -> bool:
        return not any(
            (
                self.orcid,
                self.openalex_author_id,
                self.semantic_scholar_author_id,
                self.scopus_author_id,
            )
        )


class AuthorQuery(BaseModel):
    # Full or partial name; every backend queried here performs fuzzy/substring
    # matching server-side, so "jane smith" or even "j smith" is a valid query.
    name: str | None = None
    ids: AuthorIdentifier | None = None

    def has_criteria(self) -> bool:
        return bool(self.name) or (self.ids is not None and not self.ids.is_empty())

    @model_validator(mode="after")
    def _require_criteria(self) -> AuthorQuery:
        if not self.has_criteria():
            raise ValueError("AuthorQuery must specify a name and/or at least one id")
        return self


class AuthorProfile(BaseModel):
    provider: str
    name: str
    external_ids: dict[str, str] = Field(default_factory=dict)
    orcid: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    paper_count: int | None = None
    citation_count: int | None = None
    h_index: int | None = None
    homepage_url: str | None = None
    raw: dict | None = None
