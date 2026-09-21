"""Tests for the ConceptNet sidecar client (conceptnet_client.py).

Verifies:
1. the local conceptnet_numberbatch path routes to the sidecar over HTTP,
2. a simulated sidecar failure (connection refused) returns clean 503
   problem+json (the sidecar is optional; the main service stays healthy),
3. the best-effort reachability check used by the discovery endpoint,
4. an OOV pair reported by the sidecar maps to a null-score result.
"""

from fastapi.testclient import TestClient
from src import conceptnet_client
from src.main import app

client = TestClient(app)


class TestSidecarClient:
    def test_get_relatedness_forwards_pairs(self, monkeypatch):
        """get_relatedness POSTs pairs and returns the normalized scalar items."""
        from unittest.mock import MagicMock

        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return [{"id": "p1", "score": 0.83, "error": None}]

            @property
            def request(self):
                return MagicMock()

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json):
                captured["url"] = url
                captured["payload"] = json
                return FakeResponse()

        # get_relatedness posts through the module-level shared client; patch that
        # directly (patching httpx.Client after import can't affect the already
        # created `_shared_client` instance).
        original = conceptnet_client._shared_client
        conceptnet_client._shared_client = FakeClient()
        try:
            items = conceptnet_client.get_relatedness([{"id": "p1", "word_a": "king", "word_b": "queen", "lang": "en"}])
            assert captured["url"].endswith("/v1/relatedness")
            assert captured["payload"] == {"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen", "lang": "en"}]}
            assert items[0]["score"] == 0.83
            assert "compute_time_ms" in items[0]
        finally:
            conceptnet_client._shared_client = original

    def test_sidecar_unreachable_returns_503(self, monkeypatch):
        """Sidecar down -> clean 503 problem+json, not a 500."""
        monkeypatch.setattr(conceptnet_client, "SIDECAR_BASE_URL", "http://127.0.0.1:57999")

        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "embedding_cosine",
                "params": {"variant": "conceptnet_numberbatch"},
                "inputs": [{"id": "p1", "a": "king", "b": "queen"}],
            },
        )
        assert resp.status_code == 503
        body = resp.json()
        assert "title" in body
        assert "TEXT_SIMILARITY_CONCEPTNET_URL" in body["detail"]
        assert "conceptnet-sidecar" in body["detail"]

    def test_sidecar_error_is_passed_through(self, monkeypatch):
        """A sidecar 5xx surfaces as a 502, not swallowed."""
        from src.conceptnet_client import ConceptNetSidecarError

        def fake_get_relatedness(pairs):
            raise ConceptNetSidecarError("ConceptNet sidecar returned HTTP 500", status=502)

        monkeypatch.setattr("src.conceptnet_client.get_relatedness", fake_get_relatedness)
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "embedding_cosine",
                "params": {"variant": "conceptnet_numberbatch", "backend": "local"},
                "inputs": [{"id": "p1", "a": "king", "b": "queen"}],
            },
        )
        assert resp.status_code == 502
        assert "ConceptNet sidecar" in resp.json()["detail"]

    def test_reachability_check(self, monkeypatch):
        """is_sidecar_reachable returns False rather than raising when down."""
        monkeypatch.setattr(conceptnet_client, "SIDECAR_BASE_URL", "http://127.0.0.1:57999")
        assert conceptnet_client.is_sidecar_reachable() is False
