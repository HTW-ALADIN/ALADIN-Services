"""Tests for the text similarity service API skeleton."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "text-similarity-service"


def test_algorithms_catalog():
    """GET /v1/text/algorithms lists all 23 algorithm families with backends."""
    resp = client.get("/v1/text/algorithms")
    assert resp.status_code == 200
    catalog = resp.json()
    algorithms = {e["algorithm"] for e in catalog}
    assert len(algorithms) == 23
    # Verify all entries have required fields
    for entry in catalog:
        assert "operation" in entry
        assert "algorithm" in entry
        assert "backend" in entry
        assert "families" in entry
        assert "result_type" in entry
        assert "description" in entry
    # Verify specific algorithms exist
    assert "levenshtein" in algorithms
    assert "sbert_cosine" in algorithms
    assert "synonym" in algorithms
    assert "semantic_search" in algorithms
    assert "sequence_alignment" in algorithms
    assert "compression_ncd" in algorithms
    assert "phonetic" in algorithms
    assert "tfidf_cosine" in algorithms
    assert "bertscore" in algorithms
    assert "topic_model" in algorithms
    assert "structural_stylistic" in algorithms
    # levenshtein should have nltk + rapidfuzz + textdistance backends
    lev = [e for e in catalog if e["algorithm"] == "levenshtein"]
    assert {e["backend"] for e in lev} == {"nltk", "rapidfuzz", "textdistance"}
    # the first backend is the auto-selected default
    assert lev[0]["default"] is True


def test_compute_levenshtein():
    """POST /v1/text/distance with levenshtein returns a similarity result."""
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "levenshtein",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "levenshtein"
    assert body["backend"] == "nltk"  # auto-selected default backend
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "p1"
    assert body["results"][0]["result"]["raw"] == 3


def test_compute_levenshtein_rapidfuzz():
    """POST /v1/text/distance with an explicit backend."""
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "levenshtein",
            "backend": "rapidfuzz",
            "params": {},
            "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "rapidfuzz"
    assert body["results"][0]["result"]["raw"] == 3


def test_compute_batch():
    """Batch inputs return one result per input."""
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "levenshtein",
            "params": {},
            "inputs": [
                {"id": "p1", "a": "kitten", "b": "sitting"},
                {"id": "p2", "a": "hello", "b": "hello"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][1]["result"]["raw"] == 0


def test_compute_unknown_algorithm():
    """Unknown algorithm returns 400 problem+json."""
    resp = client.post(
        "/v1/text/distance",
        json={"algorithm": "nonexistent", "params": {}, "inputs": [{"id": "p1", "a": "a", "b": "b"}]},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown algorithm" in body["title"]


def test_compute_unsupported_backend():
    """Unsupported backend for an algorithm returns 400."""
    resp = client.post(
        "/v1/text/distance",
        json={"algorithm": "levenshtein", "backend": "nonexistent", "params": {}, "inputs": [{"id": "p1", "a": "a", "b": "b"}]},
    )
    assert resp.status_code == 400


def test_compute_fuzzy_extract():
    """POST /v1/text/retrieval with fuzzy_extract."""
    resp = client.post(
        "/v1/text/retrieval",
        json={
            "algorithm": "fuzzy_extract",
            "params": {},
            "inputs": [{"id": "q1", "query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "fuzzy_extract"
    assert body["results"][0]["result"]["count"] > 0


def test_compute_synonym():
    """POST /v1/text/lexical with synonym."""
    try:
        from nltk.corpus import wordnet as wn

        _ = wn.synsets("dog")
    except LookupError:
        pytest.skip("NLTK wordnet data not downloaded")
    resp = client.post(
        "/v1/text/lexical",
        json={"algorithm": "synonym", "params": {}, "inputs": [{"id": "w1", "word": "dog"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["result"]["count"] > 0
