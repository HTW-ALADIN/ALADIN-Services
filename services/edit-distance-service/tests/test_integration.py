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
        resp = client.post("/v1/text/distance", json={
            "algorithm": "levenshtein",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "levenshtein"
        assert data["backend"] == "rapidfuzz"
        assert len(data["results"]) == 1

    def test_phonetic_returns_200(self):
        resp = client.post("/v1/text/distance", json={
            "algorithm": "phonetic_encoding",
            "params": {"scheme": "soundex"},
            "inputs": [{"id": "w1", "text": "Jellyfish"}],
        })
        assert resp.status_code == 200

    def test_batch_returns_200(self):
        resp = client.post("/v1/text/distance", json={
            "algorithm": "levenshtein",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}, {"id": "p2", "a": "flaw", "b": "lawn"}],
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2

    def test_missing_algorithm_returns_422(self):
        resp = client.post("/v1/text/distance", json={"inputs": [{"id": "p1", "a": "a", "b": "b"}]})
        assert resp.status_code == 422

    def test_unknown_algorithm_returns_400(self):
        resp = client.post("/v1/text/distance", json={"algorithm": "nonexistent", "inputs": [{"id": "p1", "a": "a", "b": "b"}]})
        assert resp.status_code == 400

    def test_oversized_input_string_returns_422(self):
        from src.models import MAX_TEXT_LENGTH

        resp = client.post("/v1/text/distance", json={
            "algorithm": "levenshtein",
            "inputs": [{"id": "p1", "a": "x" * (MAX_TEXT_LENGTH + 1), "b": "y"}],
        })
        assert resp.status_code == 422

    def test_oversized_batch_returns_422(self):
        from src.models import MAX_BATCH_SIZE

        inputs = [{"id": f"p{i}", "a": "a", "b": "b"} for i in range(MAX_BATCH_SIZE + 1)]
        resp = client.post("/v1/text/distance", json={"algorithm": "levenshtein", "inputs": inputs})
        assert resp.status_code == 422


class TestGedDiscovery:
    def test_list_ged_algorithms(self):
        resp = client.get("/v1/graphs/algorithms")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["algorithm"]


class TestGedCompute:
    def test_networkx_returns_200(self):
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_astar",
            "params": {"mode": "exact", "timeout_ms": 5000},
            "graphs": [{"id": "pair-1", "g1": {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"source": "A", "target": "B"}]}, "g2": {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}], "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]}}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "ged_astar"
        assert len(data["results"]) == 1
        assert "id" in data

    def test_missing_algorithm_returns_422(self):
        resp = client.post("/v1/graphs/distance", json={
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}]}, "g2": {"nodes": [{"id": "B"}]}}],
        })
        assert resp.status_code == 422

    def test_networkx_adjacency_matrix(self):
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_astar",
            "params": {"mode": "exact", "timeout_ms": 5000},
            "graphs": [{"id": "pair-1", "g1": {"format": "adjacency_matrix", "matrix": [[0,1],[1,0]], "node_labels": ["A","B"]}, "g2": {"format": "adjacency_matrix", "matrix": [[0,1,1],[1,0,1],[1,1,0]], "node_labels": ["A","B","C"]}}],
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_networkx_node_link(self):
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_astar",
            "params": {"mode": "exact", "timeout_ms": 5000},
            "graphs": [{"id": "pair-1", "g1": {"format": "node_link", "nodes": [{"id":"A"}, {"id":"B"}], "links": [{"source":"A","target":"B"}]}, "g2": {"format": "node_link", "nodes": [{"id":"A"}, {"id":"B"}, {"id":"C"}], "links": [{"source":"A","target":"B"}, {"source":"B","target":"C"}]}}],
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_missing_backend_reports_error_not_silent_null(self):
        """gmatch4py is installed by default (`make prep`) but gedlib is
        manual-install-only; when a backend is absent the response must
        surface why, not just a bare null upper_bound."""
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_hausdorff",
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}], "edges": []}, "g2": {"nodes": [{"id": "A"}], "edges": []}}],
        })
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        if result["upper_bound"] is None:
            assert result["error"]

    def test_ged_heuristic_gedlib_only_method_without_explicit_backend_returns_400(self):
        """ged_heuristic defaults to the gmatch4py backend, which only
        implements BIPARTITE. Requesting a gedlib-only method (e.g. IPFP)
        without explicitly opting into "backend": "gedlib" must be rejected,
        not silently run as BIPARTITE."""
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_heuristic",
            "params": {"method": "IPFP"},
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}], "edges": []}, "g2": {"nodes": [{"id": "A"}], "edges": []}}],
        })
        assert resp.status_code == 400
        assert "IPFP" in resp.json()["detail"]

    def test_ged_heuristic_bipartite_method_default_backend_returns_200(self):
        """The gmatch4py default backend does support BIPARTITE."""
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_heuristic",
            "params": {"method": "BIPARTITE"},
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}], "edges": []}, "g2": {"nodes": [{"id": "A"}], "edges": []}}],
        })
        assert resp.status_code == 200

    def test_ged_heuristic_gedlib_method_with_explicit_backend_still_reaches_gedlib(self):
        """Explicitly requesting "backend": "gedlib" must still be allowed to
        dispatch to compute_ged (which reports its own "not installed" error
        when gedlibpy is absent, rather than being rejected upfront)."""
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_heuristic",
            "backend": "gedlib",
            "params": {"method": "IPFP"},
            "graphs": [{"id": "p1", "g1": {"nodes": [{"id": "A"}], "edges": []}, "g2": {"nodes": [{"id": "A"}], "edges": []}}],
        })
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        if result["upper_bound"] is None:
            assert result["error"]

    def test_oversized_adjacency_matrix_row_returns_422(self):
        """Field(max_length=...) on `matrix: list[list[float]]` only bounds
        the number of rows, not each row's length (regression test for the
        adjacency-matrix DoS gap)."""
        from src.models import MAX_GRAPH_NODES

        oversized_row = [0.0] * (MAX_GRAPH_NODES + 1)
        resp = client.post("/v1/graphs/distance", json={
            "algorithm": "ged_astar",
            "graphs": [{
                "id": "p1",
                "g1": {"format": "adjacency_matrix", "matrix": [oversized_row]},
                "g2": {"format": "adjacency_matrix", "matrix": [[0.0]]},
            }],
        })
        assert resp.status_code == 422

    def test_oversized_graph_batch_returns_422(self):
        from src.models import MAX_BATCH_SIZE

        graphs = [
            {"id": f"p{i}", "g1": {"nodes": [{"id": "A"}]}, "g2": {"nodes": [{"id": "A"}]}}
            for i in range(MAX_BATCH_SIZE + 1)
        ]
        resp = client.post("/v1/graphs/distance", json={"algorithm": "ged_astar", "graphs": graphs})
        assert resp.status_code == 422
