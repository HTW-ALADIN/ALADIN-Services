import asyncio

import pytest

from adapters import author_adapter
from config import settings
from core.author import AuthorIdentifier, AuthorProfile, AuthorQuery
from core.author_search_service import run_author_search
from core.paper import Paper


def _author(provider: str) -> AuthorProfile:
    return AuthorProfile(provider=provider, name="Jane Smith")


def _paper(provider: str) -> Paper:
    return Paper(
        id=f"sha256:{provider}", provider=provider, backend="scimesh", title="P", year=2024
    )


def test_run_author_search_fans_out_and_returns_authors(monkeypatch):
    async def _fake_search_authors(provider, query, credentials, max_results):
        return [_author(provider)]

    monkeypatch.setattr(author_adapter, "search_authors", _fake_search_authors)

    outcome = asyncio.run(
        run_author_search(
            query=AuthorQuery(name="Jane Smith"),
            providers=["openalex", "semantic_scholar"],
            output="authors",
            credentials=None,
            max_results=100,
            per_provider_max=50,
            include_raw=False,
        )
    )
    assert len(outcome.authors) == 2
    assert outcome.papers == []
    assert outcome.per_provider["openalex"].count == 1


def test_run_author_search_returns_papers(monkeypatch):
    async def _fake_papers_by_author(provider, query, credentials, max_results):
        return [_paper(provider)]

    monkeypatch.setattr(author_adapter, "papers_by_author", _fake_papers_by_author)

    outcome = asyncio.run(
        run_author_search(
            query=AuthorQuery(ids=AuthorIdentifier(orcid="0000-0002-1825-0097")),
            providers=["openalex"],
            output="papers",
            credentials=None,
            max_results=100,
            per_provider_max=50,
            include_raw=False,
        )
    )
    assert len(outcome.papers) == 1
    assert outcome.authors == []


def test_run_author_search_unsupported_provider_isolated():
    outcome = asyncio.run(
        run_author_search(
            query=AuthorQuery(name="Jane Smith"),
            providers=["pubmed"],
            output="authors",
            credentials=None,
            max_results=100,
            per_provider_max=50,
            include_raw=False,
        )
    )
    assert outcome.per_provider["pubmed"].errors == ["author_search_not_supported"]
    assert outcome.authors == []


def test_run_author_search_missing_credentials_isolated():
    outcome = asyncio.run(
        run_author_search(
            query=AuthorQuery(name="Jane Smith"),
            providers=["scopus"],
            output="authors",
            credentials=None,
            max_results=100,
            per_provider_max=50,
            include_raw=False,
        )
    )
    assert outcome.per_provider["scopus"].errors == ["missing_credentials"]


def test_run_author_search_hung_provider_reported_as_timeout(monkeypatch):
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.05)

    async def _hangs_forever(provider, query, credentials, max_results):
        await asyncio.sleep(10)
        return []

    monkeypatch.setattr(author_adapter, "search_authors", _hangs_forever)

    outcome = asyncio.run(
        run_author_search(
            query=AuthorQuery(name="Jane Smith"),
            providers=["openalex"],
            output="authors",
            credentials=None,
            max_results=100,
            per_provider_max=50,
            include_raw=False,
        )
    )
    assert outcome.per_provider["openalex"].errors[0].startswith("provider_timeout")


def test_run_author_search_rejects_empty_query():
    query = AuthorQuery.model_construct(name=None, ids=None)
    with pytest.raises(ValueError):
        asyncio.run(
            run_author_search(
                query=query,
                providers=["openalex"],
                output="authors",
                credentials=None,
                max_results=100,
                per_provider_max=50,
                include_raw=False,
            )
        )
