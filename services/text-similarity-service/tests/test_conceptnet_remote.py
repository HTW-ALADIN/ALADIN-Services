"""Tests for the ConceptNet remote backend of ``embedding_cosine``.

Covers:
1. the remote path with a mocked HTTP response (schema mapping, URI
   normalization, lang override, degenerate inputs)
2. error paths (timeout / network error / 429 / 5xx / malformed response ->
   502/503 problem+json, and NO silent fallback to the local gensim model)
3. ``params.backend`` validation (explicit local preserved; glove/fasttext
   reject remote; invalid value rejected)
4. the batch-size cap for ``backend: "remote"``

The integration test (real api.conceptnet.io call) is marked ``network`` and
skipped by default (``pytest -m "not network"``).
"""

import json

import pytest
from fastapi.testclient import TestClient
from src import conceptnet_api
from src.main import app
from src.similarity import compute_similarity

client = TestClient(app)


# ─── Test doubles ─────────────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text if text else (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json


class FakeClient:
    """Returns queued responses/raises queued exceptions; records calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if not self.responses:
            return FakeResponse(500, text="no responses queued")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_httpx(monkeypatch):
    """Install a fake httpx.Client factory; returns an installer for responses.

    Also neutralizes backoff/throttle sleeps so tests run instantly.
    """
    monkeypatch.setattr(conceptnet_api.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(conceptnet_api.random, "uniform", lambda *a, **k: 0.0)

    def _install(responses):
        fake = FakeClient(responses)
        monkeypatch.setattr(conceptnet_api.httpx, "Client", lambda timeout=None: fake)
        return fake

    return _install


def _assert_no_local_fallback(*args, **kwargs):
    raise AssertionError("must NOT fall back to the local gensim model")


class _FakeKeyedVectors:
    """Minimal gensim KeyedVectors stand-in (avoids the 1.2 GB download)."""

    def similarity(self, a, b):
        return 0.9 if a == b else 0.4

    def n_similarity(self, a, b):
        return 0.7


def _post_remote(params, inputs):
    return client.post(
        "/v1/text/distance",
        json={"algorithm": "embedding_cosine", "params": params, "inputs": inputs},
    )


# ─── Remote path: success ─────────────────────────────────────────────────────


class TestRemotePath:
    def test_remote_is_default_and_maps_value(self, fake_httpx, monkeypatch):
        """No params.backend -> remote; API 'value' maps onto the result schema."""
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake = fake_httpx([FakeResponse(200, {"value": 0.75, "relatedness": 0.75, "similarity": 0.75})])

        result = compute_similarity("embedding_cosine", "gensim", {"text_a": "cat", "text_b": "dog"}, {"variant": "conceptnet_numberbatch"})
        assert result["raw"] == 0.75
        assert result["similarity"] == 0.75
        assert result["distance"] == pytest.approx(0.25)
        assert result["source"] == "conceptnet_api"
        assert "compute_time_ms" in result

        url, params = fake.calls[0]
        assert "relatedness" in url
        assert params["node1"] == "/c/en/cat"
        assert params["node2"] == "/c/en/dog"

    def test_explicit_remote_backend(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake = fake_httpx([FakeResponse(200, {"value": 0.5})])
        compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "cat", "text_b": "dog"}, {"variant": "conceptnet_numberbatch", "backend": "remote"}
        )
        assert len(fake.calls) == 1

    def test_api_success_returns_mapped_schema(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake_httpx([FakeResponse(200, {"value": 0.6})])
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "gensim"  # top-level backend unchanged
        assert body["results"][0]["result"]["similarity"] == 0.6
        assert body["results"][0]["result"]["raw"] == 0.6
        assert body["results"][0]["result"]["distance"] == pytest.approx(0.4)
        assert body["results"][0]["result"]["source"] == "conceptnet_api"

    def test_multiword_normalization(self, fake_httpx):
        fake = fake_httpx([FakeResponse(200, {"value": 0.3})])
        compute_similarity(
            "embedding_cosine",
            "gensim",
            {"text_a": "cat in the hat", "text_b": "  feline  "},
            {"variant": "conceptnet_numberbatch"},
        )
        url, params = fake.calls[0]
        assert params["node1"] == "/c/en/cat_in_the_hat"  # spaces -> underscores
        assert params["node2"] == "/c/en/feline"  # stripped, case preserved

    def test_lang_override(self, fake_httpx):
        fake = fake_httpx([FakeResponse(200, {"value": 0.2})])
        compute_similarity(
            "embedding_cosine",
            "gensim",
            {"text_a": "Haus", "text_b": "Wohnung"},
            {"variant": "conceptnet_numberbatch", "lang": "de"},
        )
        url, params = fake.calls[0]
        assert params["node1"] == "/c/de/Haus"
        assert params["node2"] == "/c/de/Wohnung"

    def test_empty_inputs_do_not_hit_api(self, fake_httpx):
        fake = fake_httpx([])
        both_empty = compute_similarity("embedding_cosine", "gensim", {"text_a": "  ", "text_b": ""}, {"variant": "conceptnet_numberbatch"})
        assert both_empty["similarity"] == 1.0
        one_empty = compute_similarity("embedding_cosine", "gensim", {"text_a": "cat", "text_b": ""}, {"variant": "conceptnet_numberbatch"})
        assert one_empty["similarity"] == 0.0
        assert fake.calls == []  # no HTTP call for degenerate inputs


# ─── Local path: unchanged behaviour ─────────────────────────────────────────


class TestLocalPath:
    def test_explicit_local_uses_gensim(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return _FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        from src.model_cache import clear_all

        clear_all()
        result = compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "conceptnet_numberbatch", "backend": "local"}
        )
        assert captured == ["conceptnet-numberbatch-17-06-300"]
        assert result["similarity"] == 0.4
        assert "source" not in result  # local results keep the plain schema


# ─── params.backend validation ────────────────────────────────────────────────


class TestValidation:
    def test_glove_rejects_remote(self, fake_httpx):
        fake = fake_httpx([])
        with pytest.raises(ValueError, match="no public similarity API"):
            compute_similarity("embedding_cosine", "gensim", {"text_a": "cat", "text_b": "dog"}, {"variant": "glove", "backend": "remote"})
        assert fake.calls == []  # no remote call attempted

    def test_fasttext_rejects_remote(self, fake_httpx):
        fake = fake_httpx([])
        with pytest.raises(ValueError, match="no public similarity API"):
            compute_similarity(
                "embedding_cosine", "gensim", {"text_a": "cat", "text_b": "dog"}, {"variant": "fasttext", "backend": "remote"}
            )
        assert fake.calls == []

    def test_invalid_backend_value(self, fake_httpx):
        fake = fake_httpx([])
        with pytest.raises(ValueError, match="must be 'local' or 'remote'"):
            compute_similarity(
                "embedding_cosine",
                "gensim",
                {"text_a": "cat", "text_b": "dog"},
                {"variant": "conceptnet_numberbatch", "backend": "cloud"},
            )
        assert fake.calls == []

    def test_glove_remote_rejected_via_api(self):
        resp = _post_remote({"variant": "glove", "backend": "remote"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 400
        assert "no public similarity API" in resp.json()["detail"]


# ─── Error paths (no silent fallback) ────────────────────────────────────────


class TestErrorPaths:
    def test_timeout_returns_503(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake_httpx([conceptnet_api.httpx.ConnectTimeout("connect timed out")])
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 503
        body = resp.json()
        assert body["title"]
        assert "ConceptNet" in body["detail"]

    def test_network_error_returns_503(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake_httpx([conceptnet_api.httpx.ConnectError("connection refused")])
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 503
        assert "ConceptNet" in resp.json()["detail"]

    def test_429_after_retries_returns_503_no_fallback(self, fake_httpx, monkeypatch):
        monkeypatch.setattr(conceptnet_api, "_MAX_429_RETRIES", 2)
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake = fake_httpx([FakeResponse(429, text="rate limited")] * 3)  # initial + 2 retries
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 503
        body = resp.json()
        assert "429" in body["detail"]
        assert len(fake.calls) == 3  # retried, then gave up — no silent local fallback

    def test_http_500_returns_502(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake_httpx([FakeResponse(500, text="upstream error")])
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 502
        assert "ConceptNet" in resp.json()["detail"]

    def test_missing_value_returns_502(self, fake_httpx, monkeypatch):
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake_httpx([FakeResponse(200, {"foo": "bar"})])  # 200 but no numeric value
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, [{"id": "p1", "a": "cat", "b": "dog"}])
        assert resp.status_code == 502
        assert "missing numeric 'value'" in resp.json()["detail"]


# ─── Batch-size cap for backend="remote" ─────────────────────────────────────


class TestBatchCap:
    def test_remote_batch_over_cap_rejected(self):
        inputs = [{"id": f"p{i}", "a": "cat", "b": "dog"} for i in range(conceptnet_api.MAX_REMOTE_INPUTS + 1)]
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, inputs)
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert str(conceptnet_api.MAX_REMOTE_INPUTS) in detail
        assert "rate limit" in detail

    def test_local_batch_ignores_cap(self, monkeypatch):
        """The cap only applies to backend='remote'; local batches are unchanged."""
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return _FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        from src.model_cache import clear_all

        clear_all()
        inputs = [{"id": f"p{i}", "a": "cat", "b": "dog"} for i in range(conceptnet_api.MAX_REMOTE_INPUTS + 1)]
        resp = _post_remote({"variant": "conceptnet_numberbatch", "backend": "local"}, inputs)
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == conceptnet_api.MAX_REMOTE_INPUTS + 1

    def test_remote_batch_within_cap_ok(self, fake_httpx, monkeypatch):
        n = 3
        monkeypatch.setattr("src.model_cache.get_gensim_model", _assert_no_local_fallback)
        fake = fake_httpx([FakeResponse(200, {"value": 0.6}) for _ in range(n)])
        inputs = [{"id": f"p{i}", "a": "cat", "b": "dog"} for i in range(n)]
        resp = _post_remote({"variant": "conceptnet_numberbatch"}, inputs)
        assert resp.status_code == 200
        assert len(fake.calls) == n  # one HTTP call per input
        assert [r["id"] for r in resp.json()["results"]] == ["p0", "p1", "p2"]


# ─── Integration test (real network; skipped by default) ─────────────────────


@pytest.mark.network
class TestIntegration:
    def test_live_api_cat_dog(self):
        """Real call against api.conceptnet.io — run with `pytest -m network`."""
        resp = conceptnet_api.httpx.get(
            f"{conceptnet_api.CONCEPTNET_BASE_URL}/relatedness",
            params={"node1": "/c/en/cat", "node2": "/c/en/dog"},
            timeout=10.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "value" in data
        assert isinstance(data["value"], (int, float))
