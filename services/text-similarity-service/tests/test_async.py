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
