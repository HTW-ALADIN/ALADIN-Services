"""Tests for async computation and model lifecycle.

The model-dependent tests (sbert_cosine, cross_encoder) are marked with
@pytest.mark.model_download since they require downloading models from
HuggingFace. They are skipped by default; run with --run-model-downloads
to execute them.
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.model_cache import clear_all

client = TestClient(app)


class TestAsyncPath:
    """Async operations should return 202 then transition to completed."""

    @pytest.mark.model_download
    def test_async_returns_202(self):
        """sbert_cosine should return 202 Accepted."""
        resp = client.post(
            "/v1/compute",
            json={
                "operation": "similarity",
                "measure": "sbert_cosine",
                "input": {"text_a": "hello world", "text_b": "hi there"},
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert "id" in body

    @pytest.mark.model_download
    def test_cross_encoder_async(self):
        """cross_encoder should return 202 Accepted."""
        resp = client.post(
            "/v1/compute",
            json={
                "operation": "similarity",
                "measure": "cross_encoder",
                "input": {"text_a": "hello world", "text_b": "hi there"},
                "params": {"model_name": "cross-encoder/stsb-roberta-base"},
            },
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"

    def test_sync_returns_201(self):
        """Stateless measures should return 201 Created."""
        resp = client.post(
            "/v1/compute",
            json={
                "operation": "similarity",
                "measure": "levenshtein",
                "input": {"text_a": "a", "text_b": "b"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"


class TestModelCache:
    """Model cache should load models once and reuse them."""

    def test_clear_cache(self):
        """clear_all() should not raise."""
        clear_all()


class TestWordNetIC:
    """WordNet Information Content dependency documentation."""

    def test_ic_required_error(self):
        """res/jcn/lin variants should fail with a clear message if IC not provided."""
        from src.similarity import compute_similarity

        with pytest.raises(ValueError, match="Information Content corpus"):
            compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "res"})

    def test_ic_required_error_jcn(self):
        from src.similarity import compute_similarity

        with pytest.raises(ValueError, match="Information Content corpus"):
            compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "jcn"})

    def test_ic_required_error_lin(self):
        from src.similarity import compute_similarity

        with pytest.raises(ValueError, match="Information Content corpus"):
            compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "lin"})

    def test_path_works_without_ic(self):
        """path variant should work without IC corpus."""
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        from src.similarity import compute_similarity

        result = compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "path"})
        assert result["raw"] is not None
        assert result["raw"] > 0
