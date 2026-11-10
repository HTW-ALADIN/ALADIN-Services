import asyncio

from fastapi.testclient import TestClient

from adapters import academic_mcp_adapter, scimesh_adapter
from config import settings
from core.paper import Paper
from main import app

client = TestClient(app)


def _paper(provider: str, backend: str, title: str) -> Paper:
    return Paper(id=f"sha256:{title}", provider=provider, backend=backend, title=title, year=2024)


async def _fake_scimesh_search(provider, query, credentials, max_results):
    return [_paper(provider, "scimesh", "Scimesh Paper")]


async def _fake_academic_mcp_search(provider, query, credentials, max_results):
    return [_paper(provider, "academic_mcp", "Academic MCP Paper")]


def test_search_fans_out_across_providers(monkeypatch):
    monkeypatch.setattr(scimesh_adapter, "search", _fake_scimesh_search)
    monkeypatch.setattr(academic_mcp_adapter, "search", _fake_academic_mcp_search)

    response = client.post(
        "/v1/search",
        json={
            "query": {"text": "graph neural networks"},
            "providers": ["openalex", "pubmed"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    titles = {p["title"] for p in body["papers"]}
    assert titles == {"Scimesh Paper", "Academic MCP Paper"}
    assert body["per_provider"]["openalex"]["count"] == 1
    assert body["per_provider"]["pubmed"]["count"] == 1
    assert body["dedup_report"] is None


def test_search_missing_credentials_reported_per_provider(monkeypatch):
    monkeypatch.setattr(scimesh_adapter, "search", _fake_scimesh_search)

    response = client.post(
        "/v1/search",
        json={"query": {"text": "x"}, "providers": ["scopus"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["per_provider"]["scopus"]["count"] == 0
    assert body["per_provider"]["scopus"]["errors"] == ["missing_credentials"]
    assert body["papers"] == []


def test_search_unknown_provider_isolated(monkeypatch):
    monkeypatch.setattr(scimesh_adapter, "search", _fake_scimesh_search)

    response = client.post(
        "/v1/search",
        json={"query": {"text": "x"}, "providers": ["openalex", "not-a-provider"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["per_provider"]["not-a-provider"]["errors"] == ["unknown_provider"]
    assert len(body["papers"]) == 1


def test_search_hung_provider_reported_as_timeout_not_hang(monkeypatch):
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.05)

    async def _hangs_forever(provider, query, credentials, max_results):
        await asyncio.sleep(10)
        return []

    monkeypatch.setattr(scimesh_adapter, "search", _hangs_forever)

    response = client.post("/v1/search", json={"query": {"text": "x"}, "providers": ["openalex"]})
    assert response.status_code == 200
    body = response.json()
    assert body["per_provider"]["openalex"]["errors"][0].startswith("provider_timeout")


def test_search_with_dedup_enabled(monkeypatch):
    async def _dup_search(provider, query, credentials, max_results):
        return [
            _paper(provider, "scimesh", "Same Title"),
            _paper(provider, "scimesh", "Same Title"),
        ]

    monkeypatch.setattr(scimesh_adapter, "search", _dup_search)

    response = client.post(
        "/v1/search",
        json={
            "query": {"text": "x"},
            "providers": ["openalex"],
            "dedup": {"enabled": True, "strategy": "strict"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["papers"]) == 1
    assert body["dedup_report"]["duplicates_removed"] == 1
