"""Backward-compatibility test: Spec A payloads must behave identically on Spec B.

Per API spec §5.3: "the discriminated union schema is a strict superset, so any
client written against Spec A remains valid against Spec B".
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Replay of the Phase 2 (Spec A) test payloads
SPEC_A_PAYLOADS = [
    # levenshtein via API
    {"operation": "similarity", "measure": "levenshtein", "input": {"text_a": "kitten", "text_b": "sitting"}},
    {"operation": "similarity", "measure": "levenshtein", "backend": "rapidfuzz", "input": {"text_a": "kitten", "text_b": "sitting"}},
    # damerau_levenshtein
    {"operation": "similarity", "measure": "damerau_levenshtein", "input": {"text_a": "jellyfish", "text_b": "jellyfihs"}},
    # jaro_winkler
    {"operation": "similarity", "measure": "jaro_winkler", "input": {"text_a": "kitten", "text_b": "sitting"}},
    # hamming
    {"operation": "similarity", "measure": "hamming", "input": {"text_a": "kitten", "text_b": "kitchi"}},
    # lcs
    {"operation": "similarity", "measure": "lcs", "input": {"text_a": "kitten", "text_b": "sitting"}},
    # token_set
    {"operation": "similarity", "measure": "token_set", "input": {"text_a": "the cat sat", "text_b": "the cat"}},
    # wordnet_similarity (path)
    {
        "operation": "similarity",
        "measure": "wordnet_similarity",
        "input": {"text_a": "dog", "text_b": "cat"},
        "params": {"variant": "path"},
    },
    # retrieval: fuzzy_extract
    {"operation": "retrieval", "method": "fuzzy_extract", "input": {"query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]}},
    # retrieval: semantic_search (gensim)
    {
        "operation": "retrieval",
        "method": "semantic_search",
        "backend": "gensim",
        "input": {"query": "cat", "candidates": ["dog", "car", "house"]},
    },
    # lexical_relations: synonym
    {"operation": "lexical_relations", "relation": "synonym", "input": {"word": "dog"}},
    # lexical_relations: antonym
    {"operation": "lexical_relations", "relation": "antonym", "input": {"word": "good"}},
    # lexical_relations: hypernym
    {"operation": "lexical_relations", "relation": "hypernym", "input": {"word": "dog"}},
]


def test_spec_a_payloads_still_valid():
    """Every Spec A payload still returns 2xx on the Spec B service."""
    for payload in SPEC_A_PAYLOADS:
        resp = client.post("/v1/compute", json=payload)
        assert resp.status_code in (201, 202), f"Spec A payload {payload} failed on Spec B: HTTP {resp.status_code} — {resp.text}"


def test_spec_a_measures_still_listed():
    """All 16 Spec A tags must still be present in the Spec B catalog."""
    resp = client.get("/v1/measures")
    catalog = resp.json()
    tags = {e["tag"] for e in catalog}
    spec_a_tags = {
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
    missing = spec_a_tags - tags
    assert not missing, f"Spec A tags missing from Spec B catalog: {missing}"
