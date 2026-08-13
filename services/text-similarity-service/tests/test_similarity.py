"""Tests for similarity computation (Tier 1 stateless measures).

Tests the stateless measures that don't require model downloads:
levenshtein, damerau_levenshtein, jaro_winkler, hamming, lcs, token_set.
"""

import pytest
from src.similarity import compute_similarity


class TestLevenshtein:
    def test_nltk_default(self):
        result = compute_similarity("levenshtein", None, {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] == 3
        assert "similarity" in result
        assert "distance" in result
        assert result["compute_time_ms"] > 0

    def test_nltk_explicit(self):
        result = compute_similarity("levenshtein", "nltk", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] == 3

    def test_rapidfuzz(self):
        result = compute_similarity("levenshtein", "rapidfuzz", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] == 3

    def test_identical_strings(self):
        result = compute_similarity("levenshtein", "nltk", {"text_a": "hello", "text_b": "hello"}, {})
        assert result["raw"] == 0
        assert result["similarity"] == 1.0


class TestDamerauLevenshtein:
    def test_nltk(self):
        result = compute_similarity("damerau_levenshtein", "nltk", {"text_a": "jellyfish", "text_b": "jellyfihs"}, {})
        assert result["raw"] == 1

    def test_rapidfuzz(self):
        result = compute_similarity(
            "damerau_levenshtein",
            "rapidfuzz",
            {"text_a": "jellyfish", "text_b": "jellyfihs"},
            {},
        )
        assert result["raw"] == 1


class TestJaroWinkler:
    def test_rapidfuzz_default(self):
        result = compute_similarity("jaro_winkler", None, {"text_a": "kitten", "text_b": "sitting"}, {})
        assert 0.0 <= result["similarity"] <= 1.0

    def test_rapidfuzz_jaro_variant(self):
        result = compute_similarity(
            "jaro_winkler",
            "rapidfuzz",
            {"text_a": "kitten", "text_b": "sitting"},
            {"variant": "jaro"},
        )
        assert 0.0 <= result["similarity"] <= 1.0


class TestHamming:
    def test_rapidfuzz(self):
        result = compute_similarity("hamming", None, {"text_a": "kitten", "text_b": "kitchi"}, {})
        assert result["raw"] >= 0


class TestLCS:
    def test_rapidfuzz(self):
        result = compute_similarity("lcs", None, {"text_a": "kitten", "text_b": "sitting"}, {})
        assert 0.0 <= result["similarity"] <= 1.0


class TestTokenSet:
    def test_nltk_jaccard(self):
        result = compute_similarity(
            "token_set",
            "nltk",
            {"text_a": "the cat sat on the mat", "text_b": "the cat sat"},
            {},
        )
        assert 0.0 <= result["distance"] <= 1.0

    def test_nltk_masi(self):
        result = compute_similarity("token_set", "nltk", {"text_a": "a b c", "text_b": "a b d"}, {"variant": "masi"})
        assert 0.0 <= result["distance"] <= 1.0

    def test_nltk_binary(self):
        result = compute_similarity("token_set", "nltk", {"text_a": "a b c", "text_b": "a b d"}, {"variant": "binary"})
        assert result["distance"] in (0.0, 1.0)


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


class TestComputeErrors:
    def test_unknown_measure(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("nonexistent", None, {}, {})

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("levenshtein", "unknown_backend", {}, {})
