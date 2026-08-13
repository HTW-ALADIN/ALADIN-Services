"""Tests for the BERTScore tag.

BERTScore requires downloading a model — these tests are marked with
@pytest.mark.model_download and skipped by default.
"""

import pytest
from src.similarity import compute_similarity


class TestBertscoreNamedField:
    """BERTScore returns a P/R/F1 triple, not a bare scalar."""

    @pytest.mark.model_download
    def test_named_field_shape(self):
        """Result must have precision/recall/f1 keys."""
        result = compute_similarity(
            "bertscore", "bertscore", {"text_a": "The cat sat on the mat.", "text_b": "The cat is sitting on the mat."}, {}
        )
        assert "precision" in result
        assert "recall" in result
        assert "f1" in result
        assert 0.0 <= result["precision"] <= 1.0
        assert 0.0 <= result["recall"] <= 1.0
        assert 0.0 <= result["f1"] <= 1.0

    @pytest.mark.model_download
    def test_f1_readable(self):
        """Clients can read result.f1 for a single value."""
        result = compute_similarity(
            "bertscore", "bertscore", {"text_a": "The cat sat on the mat.", "text_b": "The cat is sitting on the mat."}, {}
        )
        assert result["f1"] > 0.5  # semantically similar sentences

    @pytest.mark.model_download
    def test_identical_texts(self):
        """Identical texts should have F1 close to 1.0."""
        result = compute_similarity(
            "bertscore", "bertscore", {"text_a": "The cat sat on the mat.", "text_b": "The cat sat on the mat."}, {}
        )
        assert result["f1"] > 0.95
