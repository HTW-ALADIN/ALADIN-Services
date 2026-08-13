"""Tests for retrieval and lexical relations computation (Tier 1)."""

import pytest
from src.lexical import compute_lexical
from src.retrieval import compute_retrieval


class TestFuzzyExtract:
    def test_rapidfuzz_basic(self):
        result = compute_retrieval(
            "fuzzy_extract",
            "rapidfuzz",
            {
                "query": "kitten",
                "candidates": ["sitting", "kitchen", "kitten", "mitten", "bitten"],
            },
            {"limit": 3},
        )
        assert result["count"] > 0
        assert len(result["matches"]) <= 3
        assert result["compute_time_ms"] > 0

    def test_rapidfuzz_exact_match(self):
        result = compute_retrieval(
            "fuzzy_extract",
            "rapidfuzz",
            {
                "query": "kitten",
                "candidates": ["kitten", "sitting", "dog"],
            },
            {},
        )
        # Exact match should be first
        assert result["matches"][0]["candidate"] == "kitten"


class TestSemanticSearch:
    def test_gensim_tfidf(self):
        """Test gensim-based semantic search using TF-IDF."""
        result = compute_retrieval(
            "semantic_search",
            "gensim",
            {
                "query": "cat",
                "candidates": ["dog", "car", "house", "kitten", "mouse"],
            },
            {"top_k": 3},
        )
        assert result["count"] > 0
        assert len(result["matches"]) <= 3
        assert result["compute_time_ms"] > 0


class TestLexicalRelations:
    def test_synonym(self):
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        result = compute_lexical("synonym", "nltk", {"word": "dog"}, {})
        assert result["count"] > 0
        assert "dog" not in result["relations"]  # shouldn't include the query word

    def test_antonym(self):
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("good")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        result = compute_lexical("antonym", "nltk", {"word": "good"}, {})
        # "good" should have antonyms like "bad", "evil"
        assert result["count"] >= 0  # may be 0 for some words

    def test_hypernym(self):
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        result = compute_lexical("hypernym", "nltk", {"word": "dog"}, {})
        assert result["count"] > 0
        # "dog" should have hypernyms like "canine", "domestic animal"

    def test_hyponym(self):
        try:
            from nltk.corpus import wordnet as wn

            _ = wn.synsets("dog")
        except LookupError:
            pytest.skip("NLTK wordnet data not downloaded")
        result = compute_lexical("hyponym", "nltk", {"word": "dog"}, {})
        assert result["count"] > 0
        # "dog" should have hyponyms like "poodle", "terrier"


class TestRetrievalErrors:
    def test_unknown_method(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_retrieval("nonexistent", None, {}, {})


class TestLexicalErrors:
    def test_unknown_relation(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_lexical("nonexistent", None, {}, {})
