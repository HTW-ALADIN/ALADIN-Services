from fastapi.testclient import TestClient

from adapters import author_adapter
from core.author import AuthorProfile
from core.paper import Paper
from main import app

client = TestClient(app)


def _author(provider: str, name: str) -> AuthorProfile:
    return AuthorProfile(provider=provider, name=name, external_ids={provider: "id-1"})


def _paper(provider: str, title: str) -> Paper:
    return Paper(id=f"sha256:{title}", provider=provider, backend="scimesh", title=title, year=2024)


async def _fake_search_authors(provider, query, credentials, max_results):
    return [_author(provider, "Jane Smith")]


async def _fake_papers_by_author(provider, query, credentials, max_results):
    return [_paper(provider, "Some Paper")]


def test_author_search_by_name_returns_authors(monkeypatch):
    monkeypatch.setattr(author_adapter, "search_authors", _fake_search_authors)

    response = client.post(
        "/v1/authors/search",
        json={"query": {"name": "Jane Smith"}, "providers": ["openalex", "semantic_scholar"]},
    )
    assert response.status_code == 200
    body = response.json()
    names = {a["name"] for a in body["authors"]}
    assert names == {"Jane Smith"}
    assert body["papers"] == []
    assert body["per_provider"]["openalex"]["count"] == 1


def test_author_search_by_id_returns_authors(monkeypatch):
    monkeypatch.setattr(author_adapter, "search_authors", _fake_search_authors)

    response = client.post(
        "/v1/authors/search",
        json={
            "query": {"ids": {"orcid": "0000-0002-1825-0097"}},
            "providers": ["openalex"],
        },
    )
    assert response.status_code == 200
    assert response.json()["authors"][0]["provider"] == "openalex"


def test_author_search_output_papers(monkeypatch):
    monkeypatch.setattr(author_adapter, "papers_by_author", _fake_papers_by_author)

    response = client.post(
        "/v1/authors/search",
        json={
            "query": {"name": "Jane Smith"},
            "providers": ["semantic_scholar"],
            "output": "papers",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["authors"] == []
    assert [p["title"] for p in body["papers"]] == ["Some Paper"]


def test_author_search_requires_name_or_id():
    response = client.post(
        "/v1/authors/search",
        json={"query": {}, "providers": ["openalex"]},
    )
    assert response.status_code == 422


def test_author_search_provider_without_author_support_is_isolated(monkeypatch):
    monkeypatch.setattr(author_adapter, "search_authors", _fake_search_authors)

    response = client.post(
        "/v1/authors/search",
        json={"query": {"name": "Jane Smith"}, "providers": ["openalex", "pubmed"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["per_provider"]["pubmed"]["errors"] == ["author_search_not_supported"]
    assert len(body["authors"]) == 1


def test_author_search_missing_credentials_reported_per_provider(monkeypatch):
    monkeypatch.setattr(author_adapter, "search_authors", _fake_search_authors)

    response = client.post(
        "/v1/authors/search",
        json={"query": {"name": "Jane Smith"}, "providers": ["scopus"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["per_provider"]["scopus"]["errors"] == ["missing_credentials"]
    assert body["authors"] == []
