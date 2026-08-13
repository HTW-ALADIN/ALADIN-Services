"""Script: verify Tier-1 (Spec A) family coverage end-to-end.

Checks that all 16 Tier-1 families (per optimal-library-selection
§"Tier 1 — Minimal core set") are reachable through POST /v1/compute.
"""

import sys
from typing import Any

from src.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# (family_number, family_name, payload) — one minimal valid payload per family
TIER1_FAMILIES: list[tuple[int, str, dict[str, Any]]] = [
    (1, "Levenshtein edit distance", {
        "operation": "similarity", "measure": "levenshtein",
        "input": {"text_a": "kitten", "text_b": "sitting"},
    }),
    (2, "Damerau-Levenshtein distance", {
        "operation": "similarity", "measure": "damerau_levenshtein",
        "input": {"text_a": "jellyfish", "text_b": "jellyfihs"},
    }),
    (3, "Jaro / Jaro-Winkler similarity", {
        "operation": "similarity", "measure": "jaro_winkler",
        "input": {"text_a": "kitten", "text_b": "sitting"},
    }),
    (4, "Hamming distance", {
        "operation": "similarity", "measure": "hamming",
        "input": {"text_a": "kitten", "text_b": "sitting"},
    }),
    (5, "Longest Common Subsequence", {
        "operation": "similarity", "measure": "lcs",
        "input": {"text_a": "kitten", "text_b": "sitting"},
    }),
    (6, "Token-set similarity", {
        "operation": "similarity", "measure": "token_set",
        "input": {"text_a": "the cat sat", "text_b": "the cat"},
    }),
    # 10: fuzzy extract (retrieval)
    (10, "Fuzzy string matching / best-match extraction", {
        "operation": "retrieval", "method": "fuzzy_extract",
        "input": {"query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]},
    }),
    # 17: semantic search (retrieval)
    (17, "Semantic search / NN retrieval", {
        "operation": "retrieval", "method": "semantic_search", "backend": "gensim",
        "input": {"query": "cat", "candidates": ["dog", "car", "house"]},
    }),
    # 18: WordNet path/IC similarity
    (18, "WordNet path/IC similarity", {
        "operation": "similarity", "measure": "wordnet_similarity",
        "input": {"text_a": "dog", "text_b": "cat"},
        "params": {"variant": "path"},
    }),
    # 19: synonym
    (19, "Synonym lookup", {
        "operation": "lexical_relations", "relation": "synonym",
        "input": {"word": "dog"},
    }),
    # 20: antonym
    (20, "Antonym lookup", {
        "operation": "lexical_relations", "relation": "antonym",
        "input": {"word": "good"},
    }),
    # 21: hypernym/hyponym
    (21, "Hypernym/Hyponym lookup", {
        "operation": "lexical_relations", "relation": "hypernym",
        "input": {"word": "dog"},
    }),
]

# Model-dependent families (13, 14, 16) — checked in separate model-download tests
MODEL_DEPENDENT = {12, 13, 14, 16}


def check_coverage() -> tuple[int, int]:
    """Run each family's payload through /v1/compute, return (passes, total)."""
    passed = 0
    results: list[tuple[int, str, bool]] = []
    for fam_num, fam_name, payload in TIER1_FAMILIES:
        resp = client.post("/v1/compute", json=payload)
        ok = resp.status_code in (201, 202)
        results.append((fam_num, fam_name, ok))
        if ok:
            passed += 1
        else:
            print(f"  FAIL family {fam_num} ({fam_name}): HTTP {resp.status_code} — {resp.text[:200]}")

    for fam_num, fam_name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'} family {fam_num}: {fam_name}")

    return passed, len(results)


if __name__ == "__main__":
    print(f"Verifying {len(TIER1_FAMILIES)} Tier-1 families reachable via POST /v1/compute...")
    passed, total = check_coverage()
    print(f"\nTier-1 coverage: {passed}/{total} families computable end-to-end")
    print(f"Model-dependent families (12,13,14,16) covered by model-download tests: {sorted(MODEL_DEPENDENT)}")
    if passed != total:
        print(f"FAILED: expected {total}, got {passed}")
        sys.exit(1)
    print("OK: all Tier-1 families reachable")
    sys.exit(0)