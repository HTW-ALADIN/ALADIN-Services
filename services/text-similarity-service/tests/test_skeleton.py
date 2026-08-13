"""Tests for the text similarity service skeleton."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "text-similarity-service"


def test_measures_spec_c():
    """GET /v1/measures returns 23 Spec C entries with merged backends."""
    resp = client.get("/v1/measures")
    assert resp.status_code == 200
    catalog = resp.json()
    assert len(catalog) == 23
    # Verify all entries have required fields
    for entry in catalog:
        assert "operation" in entry
        assert "tag" in entry
        assert "backends" in entry
        assert "description" in entry
    # Verify specific tags exist
    tags = {e["tag"] for e in catalog}
    assert "levenshtein" in tags
    assert "sbert_cosine" in tags
    assert "synonym" in tags
    assert "semantic_search" in tags
    assert "sequence_alignment" in tags
    assert "compression_ncd" in tags
    assert "phonetic" in tags
    assert "tfidf_cosine" in tags
    assert "bertscore" in tags
    assert "topic_model" in tags
    assert "structural_stylistic" in tags
    # Verify merged backends: levenshtein should have nltk + rapidfuzz + textdistance
    lev_entry = [e for e in catalog if e["tag"] == "levenshtein"][0]
    backend_names = {b["name"] for b in lev_entry["backends"]}
    assert "nltk" in backend_names
    assert "rapidfuzz" in backend_names
    assert "textdistance" in backend_names


def test_compute_levenshtein():
    """POST /v1/compute with levenshtein returns 201 with result."""
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "levenshtein",
            "input": {"text_a": "kitten", "text_b": "sitting"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["measure"] == "levenshtein"
    assert body["result"]["raw"] == 3


def test_compute_levenshtein_rapidfuzz():
    """POST /v1/compute with explicit backend."""
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "levenshtein",
            "backend": "rapidfuzz",
            "input": {"text_a": "kitten", "text_b": "sitting"},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["raw"] == 3


def test_get_result():
    """GET /v1/results/{id} returns stored result."""
    # First create a result
    create_resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "levenshtein",
            "input": {"text_a": "a", "text_b": "b"},
        },
    )
    assert create_resp.status_code == 201
    result_id = create_resp.json()["id"]

    # Then retrieve it
    get_resp = client.get(f"/v1/results/{result_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == result_id


def test_delete_result():
    """DELETE /v1/results/{id} removes stored result."""
    create_resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "levenshtein",
            "input": {"text_a": "a", "text_b": "b"},
        },
    )
    result_id = create_resp.json()["id"]

    del_resp = client.delete(f"/v1/results/{result_id}")
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = client.get(f"/v1/results/{result_id}")
    assert get_resp.status_code == 404


def test_compute_invalid_operation():
    """Unknown operation returns 400 problem+json with invalidParams."""
    resp = client.post("/v1/compute", json={"operation": "unknown_op"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["title"] == "Invalid operation"
    assert "invalidParams" in body
    assert body["invalidParams"][0]["name"] == "operation"


def test_compute_missing_measure():
    """Similarity without measure returns 400."""
    resp = client.post("/v1/compute", json={"operation": "similarity", "input": {"text_a": "a", "text_b": "b"}})
    assert resp.status_code == 400


def test_compute_missing_method():
    """Retrieval without method returns 400."""
    resp = client.post("/v1/compute", json={"operation": "retrieval", "input": {"query": "a", "candidates": ["b"]}})
    assert resp.status_code == 400


def test_compute_missing_relation():
    """Lexical_relations without relation returns 400."""
    resp = client.post("/v1/compute", json={"operation": "lexical_relations", "input": {"word": "dog"}})
    assert resp.status_code == 400


def test_compute_unknown_measure():
    """Unknown measure returns 400."""
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "nonexistent",
            "input": {"text_a": "a", "text_b": "b"},
        },
    )
    assert resp.status_code == 400


def test_compute_unsupported_backend():
    """Unsupported backend for measure returns 400."""
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "similarity",
            "measure": "levenshtein",
            "backend": "nonexistent",
            "input": {"text_a": "a", "text_b": "b"},
        },
    )
    assert resp.status_code == 400


def test_compute_fuzzy_extract():
    """POST /v1/compute with retrieval/fuzzy_extract."""
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "retrieval",
            "method": "fuzzy_extract",
            "input": {"query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "retrieval"
    assert body["result"]["count"] > 0


def test_compute_synonym():
    """POST /v1/compute with lexical_relations/synonym."""
    try:
        from nltk.corpus import wordnet as wn

        _ = wn.synsets("dog")
    except LookupError:
        pytest.skip("NLTK wordnet data not downloaded")
    resp = client.post(
        "/v1/compute",
        json={
            "operation": "lexical_relations",
            "relation": "synonym",
            "input": {"word": "dog"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "lexical_relations"
    assert body["result"]["count"] > 0
