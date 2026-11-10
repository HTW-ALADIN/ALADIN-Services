from fastapi.testclient import TestClient

from adapters import scimesh_adapter
from core.paper import Paper
from main import app

client = TestClient(app)


def _paper(paper_id: str, doi: str | None = None) -> Paper:
    return Paper(
        id=f"sha256:{paper_id}",
        provider="openalex",
        backend="scimesh",
        title=paper_id,
        year=2020,
        doi=doi,
    )


def test_graph_requires_seeds_without_cursor():
    response = client.post("/v1/graph", json={"seeds": []})
    assert response.status_code == 400


def test_graph_first_call_resolves_seeds_and_returns_cursor(monkeypatch):
    async def _fake_get(provider, credentials, paper_id):
        return _paper(paper_id, doi=paper_id)

    async def _fake_citations(provider, credentials, paper_id, direction, max_results):
        return [_paper(f"{paper_id}-cited", doi=f"{paper_id}-cited")]

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)
    monkeypatch.setattr(scimesh_adapter, "citations", _fake_citations)

    response = client.post(
        "/v1/graph",
        json={
            "seeds": [{"provider": "openalex", "paper_id": "10.1/seed"}],
            "max_depth": 2,
            "max_nodes_per_level": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["depth_reached"] == 0
    assert body["done"] is False
    assert body["cursor"] is not None
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["is_seed"] is True

    # Advance one level using the returned cursor.
    response_2 = client.post("/v1/graph", json={"cursor": body["cursor"]})
    assert response_2.status_code == 200
    body_2 = response_2.json()
    assert body_2["depth_reached"] == 1
    assert len(body_2["nodes"]) >= 1
    assert len(body_2["edges"]) >= 1


def test_graph_seed_without_citation_support_is_skipped(monkeypatch):
    async def _fake_get(provider, credentials, paper_id):
        return _paper(paper_id, doi=paper_id)

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)

    response = client.post(
        "/v1/graph",
        json={"seeds": [{"provider": "arxiv", "paper_id": "2401.00001"}], "max_depth": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["done"] is True
    assert "arxiv" in body["stats"]["skipped_no_citation_support"]


def test_graph_invalid_cursor_returns_400():
    response = client.post("/v1/graph", json={"cursor": "not-a-real-cursor"})
    assert response.status_code == 400
