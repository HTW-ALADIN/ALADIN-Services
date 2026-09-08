"""Tests for model lifecycle and WordNet IC handling.

The API is fully synchronous/stateless; the model-dependent algorithms
(sbert_cosine, cross_encoder, bertscore) are marked with
@pytest.mark.model_download since they require downloading models from
HuggingFace. They are skipped by default.
"""

import pytest
from src.model_cache import clear_all


class TestModelCache:
    """Model cache should load models once and reuse them."""

    def test_clear_cache(self):
        """clear_all() should not raise."""
        clear_all()


class TestWordNetIC:
    """WordNet Information Content handling.

    The IC-based variants (res/jcn/lin) load the Information-Content corpus
    server-side (cached), so a caller never has to supply it (a raw IC object
    cannot cross the JSON boundary — its integer synset-offset keys are coerced
    to strings). ``params.ic`` is an optional published-corpus-filename override.
    """

    @pytest.fixture(autouse=True)
    def _require_wordnet(self):
        """Skip when the NLTK wordnet corpus is not available (offline run)."""
        pytest.importorskip("nltk")
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")

    @pytest.mark.parametrize("variant", ["res", "jcn", "lin"])
    def test_ic_variants_work_without_explicit_corpus(self, variant):
        """res/jcn/lin compute a real value out of the box; no corpus supplied."""
        from src.similarity import compute_similarity

        result = compute_similarity(
            "wordnet_similarity",
            "nltk",
            {"text_a": "dog", "text_b": "cat"},
            {"variant": variant},
        )
        assert result["raw"] is not None, f"{variant} should compute server-side"

    @pytest.mark.parametrize("variant", ["res", "jcn", "lin"])
    def test_ic_variants_accept_corpus_name_override(self, variant):
        """An explicit published corpus filename via params.ic is honoured."""
        from src.similarity import compute_similarity

        result = compute_similarity(
            "wordnet_similarity",
            "nltk",
            {"text_a": "dog", "text_b": "cat"},
            {"variant": variant, "ic": "ic-brown.dat"},
        )
        assert result["raw"] is not None

    def test_path_works_without_ic(self):
        """path variant should work without IC corpus."""
        from src.similarity import compute_similarity

        result = compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "path"})
        assert result["raw"] is not None
        assert result["raw"] > 0


@pytest.mark.model_download
class TestPytorchProfileCompute:
    """End-to-end compute through the pytorch profile's actual model path.

    These exercise the text-similarity-pytorch build: the profile is switched
    to ``pytorch`` and a real SBERT model runs a request. Requires the ``[model]``
    extra + a model download, so they carry the ``model_download`` marker and are
    deselected in the default/offline suite (``-m "not model_download ..."``).
    Run explicitly with ``-m model_download`` — e.g. in the pytorch-image CI job.
    """

    @pytest.fixture(autouse=True)
    def _require_extra_and_profile(self, profile_client):
        pytest.importorskip("sentence_transformers")
        self.client = profile_client("pytorch")

    def test_sbert_cosine_returns_similarity(self):
        resp = self.client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "sbert_cosine",
                "params": {"model_name": "all-MiniLM-L6-v2"},
                "inputs": [{"id": "p1", "a": "a cat sits on a mat", "b": "a cat sits on a mat"}],
            },
        )
        assert resp.status_code == 200, resp.text
        sim = resp.json()["results"][0]["result"]["similarity"]
        assert sim > 0.99

    def test_semantic_search_returns_matches(self):
        resp = self.client.post(
            "/v1/similarity/text/retrieval",
            json={
                "algorithm": "semantic_search",
                "params": {"model_name": "all-MiniLM-L6-v2", "top_k": 2},
                "inputs": [{"id": "q1", "query": "cat", "candidates": ["a cat", "a dog", "a house"]}],
            },
        )
        assert resp.status_code == 200, resp.text
        matches = resp.json()["results"][0]["result"]["matches"]
        assert matches and matches[0]["score"] > matches[-1]["score"]

    def test_cross_encoder_returns_score(self):
        resp = self.client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "cross_encoder",
                "params": {"model_name": "cross-encoder/stsb-roberta-base"},
                "inputs": [{"id": "p1", "a": "a man is playing a guitar", "b": "a woman is cooking"}],
            },
        )
        assert resp.status_code == 200, resp.text
        assert "raw" in resp.json()["results"][0]["result"]
