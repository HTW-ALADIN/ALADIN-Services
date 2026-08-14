"""Tests for the DKPro sidecar proxy.

Verifies:
1. topic_model requests route to the sidecar and return a normal Result envelope
2. a simulated sidecar failure (connection refused) returns a clean problem+json
   (502/503), not a 500 with an unhandled exception.
"""

from fastapi.testclient import TestClient
from src.dkpro_proxy import is_dkpro_request
from src.main import app

client = TestClient(app)


class TestIsDkproRequest:
    def test_topic_model_always_routes(self):
        assert is_dkpro_request("topic_model", None) is True
        assert is_dkpro_request("topic_model", "dkpro") is True

    def test_structural_stylistic_always_routes(self):
        assert is_dkpro_request("structural_stylistic", None) is True

    def test_backend_extension_routes_when_dkpro(self):
        assert is_dkpro_request("tfidf_cosine", "dkpro") is True
        assert is_dkpro_request("wordnet_similarity", "dkpro") is True

    def test_backend_extension_does_not_route_for_other_backends(self):
        assert is_dkpro_request("tfidf_cosine", "sklearn") is False
        assert is_dkpro_request("wordnet_similarity", "nltk") is False

    def test_normal_measure_does_not_route(self):
        assert is_dkpro_request("sbert_cosine", None) is False


class TestSidecarFailure:
    def test_sidecar_unreachable_returns_502(self, monkeypatch):
        """Simulated sidecar failure: connection refused -> clean problem+json 502."""
        monkeypatch.setattr("src.dkpro_proxy.SIDECAR_BASE_URL", "http://127.0.0.1:59999")

        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "topic_model",
                "params": {"variant": "lsa"},
                "inputs": [{"id": "p1", "a": "The cat sat on the mat.", "b": "A dog sat on the rug."}],
            },
        )
        assert resp.status_code in (502, 503)
        body = resp.json()
        assert "title" in body
        assert "detail" in body

    def test_optional_backend_sidecar_unreachable(self, monkeypatch):
        """Optional DKPro backends should also return clean 502/503 on failure."""
        monkeypatch.setattr("src.dkpro_proxy.SIDECAR_BASE_URL", "http://127.0.0.1:59999")

        for algorithm in ("tfidf_cosine", "wordnet_similarity"):
            resp = client.post(
                "/v1/similarity/text/distance",
                json={
                    "algorithm": algorithm,
                    "backend": "dkpro",
                    "params": {},
                    "inputs": [{"id": "p1", "a": "test a", "b": "test b"}],
                },
            )
            assert resp.status_code in (502, 503), f"Algorithm {algorithm} did not return 502/503 on sidecar failure: {resp.status_code}"
            body = resp.json()
            assert "title" in body
            assert "detail" in body


class TestProxyNormalization:
    def test_sidecar_response_normalized(self):
        """A healthy sidecar response is normalized into the Result envelope."""

        # Can't easily spin up the real Java sidecar here; instead verify the
        # proxy normalization function directly with a fake httpx response.
        from unittest.mock import MagicMock

        from src import dkpro_proxy

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"similarity": 0.7, "distance": 0.3, "computeTimeMs": 5.0}

            @property
            def request(self):
                return MagicMock()

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json):
                self.called_url = url
                return FakeResponse()

        original = dkpro_proxy.httpx.Client
        dkpro_proxy.httpx.Client = lambda timeout=None: FakeClient()
        try:
            result = dkpro_proxy.compute_via_sidecar(
                "topic_model",
                "lsa",
                {"text_a": "a", "text_b": "b"},
                {},
            )
        finally:
            dkpro_proxy.httpx.Client = original

        assert result["similarity"] == 0.7
        assert result["raw"] == 0.7
        assert result["distance"] == 0.3
        assert "compute_time_ms" in result
