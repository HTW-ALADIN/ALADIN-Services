"""Tests for semantic similarity computation.

Tests the stateless measures that don't require model downloads:
wordnet_similarity (path variant).
"""

import pytest
from src.similarity import compute_similarity


class TestWordNetSimilarity:
    def test_path_similarity(self):
        """Requires NLTK wordnet data."""
        pytest.importorskip("nltk")
        try:
            from nltk.corpus import wordnet as wn

            # Verify wordnet is available
            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        result = compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "path"})
        assert result["raw"] is not None
        assert result["raw"] > 0

    def test_unrelated_words_lower_than_related(self):
        """Semantic check: related words score higher than unrelated ones."""
        pytest.importorskip("nltk")
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        related = compute_similarity("wordnet_similarity", "nltk", {"text_a": "car", "text_b": "automobile"}, {"variant": "path"})
        unrelated = compute_similarity("wordnet_similarity", "nltk", {"text_a": "car", "text_b": "banana"}, {"variant": "path"})
        assert related["raw"] is not None and unrelated["raw"] is not None
        assert related["raw"] > unrelated["raw"]


class TestComputeErrors:
    def test_unknown_measure(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("nonexistent", None, {}, {})

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("wordnet_similarity", "unknown_backend", {}, {})
