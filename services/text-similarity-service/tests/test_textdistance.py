"""Tests for the scikit-learn similarity measures (tfidf_cosine)."""

from src.similarity import compute_similarity


class TestTfidfCosine:
    def test_basic(self):
        result = compute_similarity("tfidf_cosine", "sklearn", {"text_a": "the cat sat on the mat", "text_b": "the dog sat on the rug"}, {})
        assert result["raw"] is not None
        assert 0.0 <= result.get("similarity", 0) <= 1.0

    def test_identical(self):
        result = compute_similarity("tfidf_cosine", "sklearn", {"text_a": "hello world", "text_b": "hello world"}, {})
        # TF-IDF cosine of identical documents should be very close to 1.0
        assert result["similarity"] > 0.99

    def test_semantically_related_higher_than_unrelated(self):
        """TF-IDF is lexical, but shared vocabulary should rank related docs higher."""
        related = compute_similarity(
            "tfidf_cosine",
            "sklearn",
            {"text_a": "the cat sat on the mat", "text_b": "a cat on the mat"},
            {},
        )
        unrelated = compute_similarity(
            "tfidf_cosine",
            "sklearn",
            {"text_a": "the cat sat on the mat", "text_b": "quantum physics theory"},
            {},
        )
        assert related["similarity"] > unrelated["similarity"]
