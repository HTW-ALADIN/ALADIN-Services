"""Backward-compatibility test: the semantic core algorithms must remain valid."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

MODEL_ALGORITHMS = {"sbert_cosine", "cross_encoder", "bertscore", "semantic_search"}
ALL_SEMANTIC_ALGORITHMS = {
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
    "token_set_overlap",
    "bm25",
    "synonym",
    "antonym",
    "hypernym",
    "hyponym",
}


def _wordnet_available() -> bool:
    try:
        from nltk.corpus import wordnet as wn

        _ = wn.synsets("dog")
        return True
    except LookupError:
        return False


# Replay of the core semantic algorithms in the edit-distance-style request shape.
DISTANCE_PAYLOADS = [
    # wordnet_similarity (path)
    {"algorithm": "wordnet_similarity", "params": {"variant": "path"}, "inputs": [{"id": "p1", "a": "dog", "b": "cat"}]},
    # tfidf_cosine (base, no downloads)
    {"algorithm": "tfidf_cosine", "params": {}, "inputs": [{"id": "p1", "a": "the cat sat", "b": "a dog sat"}]},
]

RETRIEVAL_PAYLOADS = [
    # retrieval: bm25 (base, non-model lexical ranking — the successor of the
    # removed semantic_search TF-IDF backend)
    {
        "algorithm": "bm25",
        "params": {"top_k": 3},
        "inputs": [{"id": "q1", "query": "cat", "candidates": ["a cat", "a dog", "house"]}],
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
    """Every core payload still returns 2xx under the default cpu profile."""
    wordnet_ok = _wordnet_available()
    for payload in DISTANCE_PAYLOADS:
        if payload["algorithm"] == "wordnet_similarity" and not wordnet_ok:
            pytest.skip("NLTK wordnet data not downloaded")
        resp = client.post("/v1/similarity/text/distance", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"
    for payload in RETRIEVAL_PAYLOADS:
        resp = client.post("/v1/similarity/text/retrieval", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"
    for payload in LEXICAL_PAYLOADS:
        resp = client.post("/v1/similarity/text/lexical", json=payload)
        assert resp.status_code == 200, f"Core payload {payload} failed: HTTP {resp.status_code} — {resp.text}"


def test_cpu_catalog_lists_base_measures(profile_client):
    """The cpu (default) profile catalog lists base measures and omits PyTorch ones."""
    resp = profile_client().get("/v1/similarity/text/algorithms")
    catalog = resp.json()
    names = {e["algorithm"] for e in catalog}
    assert MODEL_ALGORITHMS.isdisjoint(names)
    assert {"wordnet_similarity", "tfidf_cosine", "bm25", "synonym", "antonym", "hypernym", "hyponym"} <= names


@pytest.mark.parametrize("profile_client", ["pytorch"], indirect=True)
def test_semantic_measures_still_listed(profile_client):
    """All canonical semantic algorithm families are present in the pytorch catalog."""
    catalog = profile_client().get("/v1/similarity/text/algorithms").json()
    algorithms = {e["algorithm"] for e in catalog}
    missing = ALL_SEMANTIC_ALGORITHMS - algorithms
    assert not missing, f"Semantic algorithms missing from catalog: {missing}"


@pytest.mark.parametrize("profile_client", ["pytorch"], indirect=True)
def test_pytorch_blocks_nothing(profile_client):
    """In the pytorch profile, PyTorch algorithms are offered, not 400-blocked."""
    nope = profile_client()
    cases = [
        ("/v1/similarity/text/distance", "sbert_cosine", {"id": "p1", "a": "a", "b": "b"}),
        ("/v1/similarity/text/retrieval", "semantic_search", {"id": "q1", "query": "a", "candidates": ["a", "b"]}),
    ]
    for path, algorithm, input_item in cases:
        resp = nope.post(path, json={"algorithm": algorithm, "params": {}, "inputs": [input_item]})
        # Not blocked by the profile guard (400 pointing at pytorch image). Either
        # the extra is installed and it computes, or the extra is missing and it
        # returns a 501 naming the install command.
        assert resp.status_code in (200, 501), f"{algorithm}: unexpected HTTP {resp.status_code} — {resp.text}"


@pytest.mark.parametrize("profile_client", ["cpu"], indirect=True)
def test_cpu_blocks_model_requests(profile_client):
    """The cpu profile rejects PyTorch algorithms with a clear 400."""
    resp = profile_client().post(
        "/v1/similarity/text/distance",
        json={"algorithm": "sbert_cosine", "params": {}, "inputs": [{"id": "p1", "a": "a", "b": "b"}]},
    )
    assert resp.status_code == 400
    assert "text-similarity-pytorch" in resp.json()["detail"]


@pytest.mark.parametrize("profile_client", ["pytorch"], indirect=True)
def test_hf_profile_omits_local_conceptnet(profile_client):
    """The "hf" build (pytorch + DISABLE_LOCAL_CONCEPTNET) still ships all HF
    models but excludes the local ConceptNet Numberbatch variant, and blocks
    requests that would need it while keeping the remote backend."""
    client = profile_client(disable_conceptnet=True)
    catalog = client.get("/v1/similarity/text/algorithms").json()
    emb = [e for e in catalog if e["algorithm"] == "embedding_cosine"]
    assert emb, "embedding_cosine should still be present in hf catalog"
    variants = emb[0].get("variants", [])
    assert variants == ["glove", "fasttext"], f"hf catalog should exclude conceptnet_numberbatch, got {variants}"

    # HF measures remain available
    names = {e["algorithm"] for e in catalog}
    assert {"sbert_cosine", "cross_encoder", "bertscore", "semantic_search"} <= names

    # Local conceptnet request is blocked with a clear pointer.
    resp = client.post(
        "/v1/similarity/text/distance",
        json={
            "algorithm": "embedding_cosine",
            "params": {"variant": "conceptnet_numberbatch"},
            "inputs": [{"id": "p1", "a": "dog", "b": "cat"}],
        },
    )
    assert resp.status_code == 400
    assert "conceptnet" in resp.json()["detail"].lower()
    assert "text-similarity-conceptnet" in resp.json()["detail"]

    # The remote backend (no local model) must NOT be blocked by the flag.
    resp_remote = client.post(
        "/v1/similarity/text/distance",
        json={
            "algorithm": "embedding_cosine",
            "params": {"variant": "conceptnet_numberbatch", "backend": "remote"},
            "inputs": [{"id": "p1", "a": "dog", "b": "cat"}],
        },
    )
    # It must not hit the local-model guard (a 400 about the missing model). It may
    # succeed, or fail with a network/API error (502/503) — never the local guard.
    assert resp_remote.status_code != 400 or "not ship" not in resp_remote.json().get("detail", ""), resp_remote.text
