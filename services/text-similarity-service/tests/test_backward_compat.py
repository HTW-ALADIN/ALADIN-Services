"""Backward-compatibility test: the original core algorithms must remain valid."""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Replay of the original core algorithms in the edit-distance-style request shape.
DISTANCE_PAYLOADS = [
    # levenshtein via API (auto-selected default backend)
    {"algorithm": "levenshtein", "params": {}, "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}]},
    # levenshtein with an explicit backend
    {"algorithm": "levenshtein", "backend": "rapidfuzz", "params": {}, "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}]},
    # damerau_levenshtein
    {"algorithm": "damerau_levenshtein", "params": {}, "inputs": [{"id": "p1", "a": "jellyfish", "b": "jellyfihs"}]},
    # jaro_winkler
    {"algorithm": "jaro_winkler", "params": {}, "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}]},
    # hamming
    {"algorithm": "hamming", "params": {}, "inputs": [{"id": "p1", "a": "kitten", "b": "kitchi"}]},
    # lcs
    {"algorithm": "lcs", "params": {}, "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}]},
    # token_set
    {"algorithm": "token_set", "params": {}, "inputs": [{"id": "p1", "a": "the cat sat", "b": "the cat"}]},
    # wordnet_similarity (path)
    {"algorithm": "wordnet_similarity", "params": {"variant": "path"}, "inputs": [{"id": "p1", "a": "dog", "b": "cat"}]},
]

RETRIEVAL_PAYLOADS = [
    # retrieval: fuzzy_extract
    {
        "algorithm": "fuzzy_extract",
        "params": {},
        "inputs": [{"id": "q1", "query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]}],
    },
    # retrieval: semantic_search (gensim)
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


def test_base_measures_still_listed():
    """All 16 core algorithm families must still be present in the catalog."""
    resp = client.get("/v1/text/algorithms")
    catalog = resp.json()
    algorithms = {e["algorithm"] for e in catalog}
    base_algorithms = {
        "levenshtein",
        "damerau_levenshtein",
        "jaro_winkler",
        "hamming",
        "lcs",
        "token_set",
        "embedding_cosine",
        "sbert_cosine",
        "wmd",
        "cross_encoder",
        "wordnet_similarity",
        "fuzzy_extract",
        "semantic_search",
        "synonym",
        "antonym",
        "hypernym",
    }
    missing = base_algorithms - algorithms
    assert not missing, f"Core algorithms missing from catalog: {missing}"
