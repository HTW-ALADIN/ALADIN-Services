"""Tests for Spec B similarity measures (textdistance + scikit-learn additions)."""

from src.similarity import compute_similarity


def _raw_or_similarity(result):
    """Helper to get a safe comparable value."""
    return result.get("similarity", result.get("raw", 0))


class TestSequenceAlignment:
    def test_needleman_wunsch(self):
        result = compute_similarity("sequence_alignment", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] is not None
        assert "similarity" in result
        assert "distance" in result

    def test_smith_waterman(self):
        result = compute_similarity(
            "sequence_alignment", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {"variant": "smith_waterman"}
        )
        assert result["raw"] is not None

    def test_gotoh(self):
        result = compute_similarity("sequence_alignment", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {"variant": "gotoh"})
        assert result["raw"] is not None


class TestCompressionNCD:
    def test_entropy(self):
        result = compute_similarity("compression_ncd", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] is not None
        assert 0.0 <= _raw_or_similarity(result) <= 1.0


class TestPhonetic:
    def test_editex(self):
        result = compute_similarity("phonetic", "textdistance", {"text_a": "smith", "text_b": "smyth"}, {"variant": "editex"})
        assert result["raw"] is not None

    def test_mra(self):
        result = compute_similarity("phonetic", "textdistance", {"text_a": "smith", "text_b": "smyth"}, {"variant": "mra"})
        assert result["raw"] is not None


class TestTfidfCosine:
    def test_basic(self):
        result = compute_similarity("tfidf_cosine", "sklearn", {"text_a": "the cat sat on the mat", "text_b": "the dog sat on the rug"}, {})
        assert result["raw"] is not None
        assert 0.0 <= result.get("similarity", 0) <= 1.0

    def test_identical(self):
        result = compute_similarity("tfidf_cosine", "sklearn", {"text_a": "hello world", "text_b": "hello world"}, {})
        # TF-IDF cosine of identical documents should be very close to 1.0
        assert result["similarity"] > 0.99


class TestTextdistanceBackends:
    """Test textdistance as an alternative backend on existing Tier-1 tags."""

    def test_levenshtein_textdistance(self):
        result = compute_similarity("levenshtein", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert result["raw"] == 3

    def test_damerau_levenshtein_textdistance(self):
        result = compute_similarity("damerau_levenshtein", "textdistance", {"text_a": "jellyfish", "text_b": "jellyfihs"}, {})
        assert result["raw"] == 1

    def test_jaro_winkler_textdistance(self):
        result = compute_similarity("jaro_winkler", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert 0.0 <= result["similarity"] <= 1.0

    def test_hamming_textdistance(self):
        result = compute_similarity("hamming", "textdistance", {"text_a": "kitten", "text_b": "kitchi"}, {})
        assert result["raw"] >= 0

    def test_lcs_textdistance(self):
        result = compute_similarity("lcs", "textdistance", {"text_a": "kitten", "text_b": "sitting"}, {})
        assert 0.0 <= result["similarity"] <= 1.0

    def test_token_set_textdistance_jaccard(self):
        result = compute_similarity("token_set", "textdistance", {"text_a": "cat dog", "text_b": "cat dog mouse"}, {})
        assert 0.0 <= result["similarity"] <= 1.0

    def test_default_backend_unchanged(self):
        """Default backend for levenshtein should still be nltk."""
        from src.similarity import DEFAULT_BACKENDS

        assert DEFAULT_BACKENDS["levenshtein"] == "nltk"
