"""Backward-compatibility test: the semantic core algorithms must remain valid."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Replay of the core semantic algorithms in the edit-distance-style request shape.
DISTANCE_PAYLOADS = [
    # wordnet_similarity (path)
    {"algorithm": "wordnet_similarity", "params": {"variant": "path"}, "inputs": [{"id": "p1", "a": "dog", "b": "cat"}]},
    # tfidf_cosine (base, no downloads)
    {"algorithm": "tfidf_cosine", "params": {}, "inputs": [{"id": "p1", "a": "the cat sat", "b": "a dog sat"}]},
]

RETRIEVAL_PAYLOADS = [
    # retrieval: semantic_search (gensim/TF-IDF)
    {
        "algorithm": "semantic_search",
        "backend": "gensim",
        "params": {},
        "inputs": [{"id": "q1", "query": "cat", "candidates": ["dog", "car", "house"]}],
    },
]

LEXICAL_PAYLOADS = [
    # lexical_relations: synonym
    {"algorithm": "synonym", "params": {}, "inputs": [{"id": "w1", "word": "dog"}]},
    # lexical_relations: antonym
    {"algorithm": "antonym", "params": {}, "inputs": [{"id": "w1", "word": "good"}]},
    # lexical_relations: hypernym
    {"algorithm": "hypernym", "params": {}, "inputs": [{"id": "w1", "word": "dog"}]},
]


def test_base_payloads_still_valid():
    """Every core payload still returns 2xx."""
    for payload in DISTANCE_PAYLOADS:
        resp = client.post("/v1/text/distance", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"
    for payload in RETRIEVAL_PAYLOADS:
        resp = client.post("/v1/text/retrieval", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"
    for payload in LEXICAL_PAYLOADS:
        resp = client.post("/v1/text/lexical", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"


def test_semantic_measures_still_listed():
    """All 13 semantic algorithm families must still be present in the catalog."""
    resp = client.get("/v1/text/algorithms")
    catalog = resp.json()
    algorithms = {e["algorithm"] for e in catalog}
    semantic_algorithms = {
        "wordnet_similarity",
        "embedding_cosine",
        "sbert_cosine",
        "wmd",
        "cross_encoder",
        "tfidf_cosine",
        "bertscore",
        "topic_model",
        "structural_stylistic",
        "semantic_search",
        "synonym",
        "antonym",
        "hypernym",
    }
    missing = semantic_algorithms - algorithms
    assert not missing, f"Semantic algorithms missing from catalog: {missing}"
