"""Integration tests for the edit distance service API.

Tests HTTP-layer behavior (status codes, routing, error responses).
Does NOT duplicate unit-test value assertions from test_text/compare.py.
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestTextDiscovery:
    def test_list_text_algorithms(self):
        resp = client.get("/v1/text/algorithms")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["algorithm"]
        assert data[0]["backend"]


class TestTextCompare:
    def test_levenshtein_returns_200(self):
        resp = client.post("/v1/text/compare", json={
            "algorithm": "levenshtein", "backend": "rapidfuzz",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "levenshtein"
        assert data["backend"] == "rapidfuzz"
        assert len(data["results"]) == 1

    def test_phonetic_returns_200(self):
        resp = client.post("/v1/text/compare", json={
            "algorithm": "phonetic_encoding", "backend": "jellyfish",
            "params": {"scheme": "soundex"},
            "inputs": [{"id": "w1", "text": "Jellyfish"}],
        })
        assert resp.status_code == 200

    def test_batch_returns_200(self):
        resp = client.post("/v1/text/compare", json={
            "algorithm": "levenshtein", "backend": "rapidfuzz",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}, {"id": "p2", "a": "flaw", "b": "lawn"}],
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2

    def test_missing_algorithm_returns_400(self):
        resp = client.post("/v1/text/compare", json={"inputs": [{"id": "p1", "a": "a", "b": "b"}]})
        assert resp.status_code == 400

    def test_unknown_algorithm_returns_400(self):
        resp = client.post("/v1/text/compare", json={"algorithm": "nonexistent", "inputs": [{"id": "p1", "a": "a", "b": "b"}]})
        assert resp.status_code == 400


class TestGedDiscovery:
    def test_list_ged_algorithms(self):
        resp = client.get("/v1/graphs/ged/algorithms")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["algorithm"]


class TestGedCompute:
    def test_networkx_returns_201(self):
        resp = client.post("/v1/graphs/ged/compute", json={
            "algorithm": "ged_astar", "backend": "networkx",
            "params": {"mode": "exact", "timeout_ms": 5000},
            "graphs": [{"id": "pair-1", "g1": {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"source": "A", "target": "B"}]}, "g2": {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}], "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]}}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["algorithm"] == "ged_astar"
        assert data["status"] == "completed"
        assert len(data["results"]) == 1
        assert "id" in data

    def test_missing_algorithm_returns_400(self):
        resp = client.post("/v1/graphs/ged/compute", json={
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}]}, "g2": {"nodes": [{"id": "B"}]}}],
        })
        assert resp.status_code == 400


class TestGedResultLifecycle:
    pass
