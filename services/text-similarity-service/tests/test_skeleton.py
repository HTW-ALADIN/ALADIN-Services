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
    """GET /v1/text/algorithms lists all 16 semantic algorithm families.

    jaccard/dice are legacy aliases of token_set_overlap and therefore do not
    count as separate families.
    """
    resp = client.get("/v1/text/algorithms")
    assert resp.status_code == 200
    catalog = resp.json()
    algorithms = {e["algorithm"] for e in catalog}
    # 16 canonical families (17 before the jaccard+dice -> token_set_overlap
    # consolidation); aliases are marked with alias_of and excluded here.
    canonical = {e["algorithm"] for e in catalog if "alias_of" not in e}
    assert len(canonical) == 16
    # Verify all entries have required fields
    for entry in catalog:
        assert "operation" in entry
        assert "algorithm" in entry
        assert "backend" in entry
        assert "families" in entry
        assert "result_type" in entry
        assert "description" in entry
        # semantic metadata for discovery
        assert "category" in entry
        assert "requires_model" in entry
        assert "requires_gpu" in entry
    # Verify semantic algorithms exist
    assert "wordnet_similarity" in algorithms
    assert "embedding_cosine" in algorithms
    assert "sbert_cosine" in algorithms
    assert "wmd" in algorithms
    assert "cross_encoder" in algorithms
    assert "tfidf_cosine" in algorithms
    assert "bertscore" in algorithms
    assert "topic_model" in algorithms
    assert "structural_stylistic" in algorithms
    assert "semantic_search" in algorithms
    assert "synonym" in algorithms
    assert "antonym" in algorithms
    assert "hypernym" in algorithms
    assert "hyponym" in algorithms
    assert "token_set_overlap" in algorithms
    assert "jaccard" in algorithms  # legacy alias of token_set_overlap
    assert "dice" in algorithms  # legacy alias of token_set_overlap
    assert "bm25" in algorithms
    # Removed char-based families must not be listed anymore
    removed = {
        "levenshtein",
        "damerau_levenshtein",
        "jaro_winkler",
        "token_set",
        "sequence_alignment",
        "compression_ncd",
        "phonetic",
        "fuzzy_extract",
    }
    for name in removed:
        assert name not in algorithms, f"{name} should have been removed"


def test_compute_tfidf():
    """POST /v1/text/distance with tfidf_cosine returns a similarity result."""
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "tfidf_cosine",
            "params": {},
            "inputs": [{"id": "p1", "a": "the cat sat on the mat", "b": "a dog sat on the rug"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "tfidf_cosine"
    assert body["backend"] == "sklearn"  # auto-selected default backend
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "p1"
    assert "similarity" in body["results"][0]["result"]


def test_compute_wordnet():
    """POST /v1/text/distance with wordnet_similarity (path)."""
    try:
        from nltk.corpus import wordnet as wn

        _ = wn.synsets("dog")
    except LookupError:
        pytest.skip("NLTK wordnet data not downloaded")
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "wordnet_similarity",
            "params": {"variant": "path"},
            "inputs": [{"id": "p1", "a": "car", "b": "automobile"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "nltk"
    assert body["results"][0]["result"]["raw"] > 0


def test_compute_batch():
    """Batch inputs return one result per input."""
    resp = client.post(
        "/v1/text/distance",
        json={
            "algorithm": "tfidf_cosine",
            "params": {},
            "inputs": [
                {"id": "p1", "a": "the cat sat", "b": "a dog sat"},
                {"id": "p2", "a": "hello world", "b": "hello world"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2


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
        json={"algorithm": "wordnet_similarity", "backend": "nonexistent", "params": {}, "inputs": [{"id": "p1", "a": "a", "b": "b"}]},
    )
    assert resp.status_code == 400


def test_compute_bm25():
    """POST /v1/text/retrieval with bm25 (base, no model) returns ranked matches.

    bm25 is the sole base-tier lexical retrieval algorithm — the former
    semantic_search TF-IDF backend was removed.
    """
    resp = client.post(
        "/v1/text/retrieval",
        json={
            "algorithm": "bm25",
            "params": {"top_k": 3},
            "inputs": [{"id": "q1", "query": "cat", "candidates": ["a cat", "a dog", "house", "kitten"]}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "bm25"
    assert body["backend"] == "builtin"  # auto-selected default backend
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
