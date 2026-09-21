"""Tests for the ConceptNet sidecar: relatedness endpoint and lazy-load/TTL eviction."""

import time

import pytest
from fastapi.testclient import TestClient
from src import main, model_cache


class FakeKeyedVectors:
    """Minimal gensim KeyedVectors stand-in (avoids the real ~1.2 GB download)."""

    def __init__(self, vocab: set[str] | None = None) -> None:
        self._vocab = vocab or {"/c/en/king", "/c/en/queen"}

    def similarity(self, a: str, b: str) -> float:
        if a not in self._vocab or b not in self._vocab:
            raise KeyError(next(w for w in (a, b) if w not in self._vocab))
        if a == b:
            return 1.0
        return 0.83


@pytest.fixture(autouse=True)
def _reset_cache():
    """The cache is a module singleton; reset it so tests don't leak into each other."""
    model_cache.cache._model = None
    model_cache.cache._loaded_at = None
    model_cache.cache._last_used = None
    yield


def _make_client(monkeypatch, model=None, ttl=None, preload=None, model_path="/fake/model") -> TestClient:
    monkeypatch.setattr(model_cache, "MODEL_PATH", model_path)
    if ttl is not None:
        monkeypatch.setattr(model_cache, "IDLE_TTL_SECONDS", ttl)
    if preload is not None:
        monkeypatch.setattr(model_cache, "PRELOAD_ON_START", preload)
    monkeypatch.setattr(model_cache.cache, "_model", model)
    monkeypatch.setattr(model_cache.cache, "_last_used", time.time() if model else None)
    return TestClient(main.app)


def test_lazy_load_first_request(monkeypatch):
    """The model is loaded on the first request, not at app start (lazy)."""
    calls = {"n": 0}

    def fake_load(self):
        calls["n"] += 1
        return FakeKeyedVectors()

    monkeypatch.setattr(model_cache, "MODEL_PATH", "/fake/model")
    monkeypatch.setattr(model_cache.cache.__class__, "_load", fake_load)
    client = TestClient(main.app)

    assert calls["n"] == 0  # nothing loaded at app construction
    resp = client.post("/v1/relatedness", json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}]})
    assert resp.status_code == 200
    assert calls["n"] == 1  # loaded on first request
    assert resp.json() == [{"id": "p1", "score": 0.83, "error": None}]


def test_ttl_eviction(monkeypatch):
    """After the TTL elapses, the model is evicted (status shows unloaded)."""
    client = _make_client(monkeypatch, model=FakeKeyedVectors(), ttl=1)
    client.post("/v1/relatedness", json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}]})
    assert model_cache.cache.status()["model_loaded"] is True

    time.sleep(1.1)
    assert model_cache.cache.evict_if_idle() is True
    assert model_cache.cache.status()["model_loaded"] is False


def test_reload_after_eviction(monkeypatch):
    """A request after eviction reloads the model automatically (no error)."""
    calls = {"n": 0}

    def fake_load(self):
        calls["n"] += 1
        return FakeKeyedVectors()

    monkeypatch.setattr(model_cache, "MODEL_PATH", "/fake/model")
    monkeypatch.setattr(model_cache.cache.__class__, "_load", fake_load)
    client = TestClient(main.app)

    first = client.post("/v1/relatedness", json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}]})
    assert first.status_code == 200
    assert calls["n"] == 1

    # Evict (simulate TTL elapse), then request again.
    model_cache.cache._model = None
    model_cache.cache._last_used = None
    second = client.post("/v1/relatedness", json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}]})
    assert second.status_code == 200
    assert calls["n"] == 2
    assert second.json() == first.json()


def test_oov_pair_does_not_fail_batch(monkeypatch):
    """An out-of-vocabulary pair yields null + error, not a batch-wide crash."""
    client = _make_client(monkeypatch, model=FakeKeyedVectors())
    resp = client.post(
        "/v1/relatedness",
        json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}, {"id": "p2", "word_a": "xxxyzz", "word_b": "queen"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["score"] == 0.83
    assert body[1]["score"] is None
    assert "oov" in body[1]["error"]


def test_identical_oov_terms_are_not_scored_as_perfect(monkeypatch):
    """Two identical out-of-vocabulary terms must NOT be scored 1.0 — the
    uri_a == uri_b shortcut would bypass the vocabulary check entirely."""
    client = _make_client(monkeypatch, model=FakeKeyedVectors())
    resp = client.post(
        "/v1/relatedness",
        json={"pairs": [{"id": "p1", "word_a": "zzznotaword", "word_b": "zzznotaword"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["score"] is None
    assert "oov" in body[0]["error"]


def test_missing_model_path_returns_503(monkeypatch):
    """A missing/unset model path yields 503, not a crash."""
    client = _make_client(monkeypatch, model=None, model_path="/does/not/exist")
    resp = client.post("/v1/relatedness", json={"pairs": [{"id": "p1", "word_a": "king", "word_b": "queen"}]})
    assert resp.status_code == 503
    assert "detail" in resp.json()
