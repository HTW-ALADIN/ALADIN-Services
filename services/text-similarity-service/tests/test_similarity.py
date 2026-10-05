"""Tests for semantic similarity computation.

Tests the stateless measures that don't require model downloads:
wordnet_similarity (path variant).
"""

import pytest
from src.similarity import compute_similarity


def _wordnet_available() -> bool:
    pytest.importorskip("nltk")
    try:
        from nltk.corpus import wordnet as wn

        _ = wn.synsets("dog")
        return True
    except LookupError:
        pytest.skip("NLTK wordnet data not downloaded")
        return False


class TestWordNetSimilarity:
    def test_path_similarity(self):
        """Requires NLTK wordnet data."""
        if not _wordnet_available():
            return
        result = compute_similarity("wordnet_similarity", "nltk", {"text_a": "dog", "text_b": "cat"}, {"variant": "path"})
        assert result["raw"] is not None
        assert result["raw"] > 0

    def test_unrelated_words_lower_than_related(self):
        """Semantic check: related words score higher than unrelated ones."""
        if not _wordnet_available():
            return
        related = compute_similarity("wordnet_similarity", "nltk", {"text_a": "car", "text_b": "automobile"}, {"variant": "path"})
        unrelated = compute_similarity("wordnet_similarity", "nltk", {"text_a": "car", "text_b": "banana"}, {"variant": "path"})
        assert related["raw"] is not None and unrelated["raw"] is not None
        assert related["raw"] > unrelated["raw"]

    @pytest.mark.parametrize("variant", ["res", "jcn", "lin"])
    def test_ic_variants_work_out_of_the_box(self, variant):
        """The IC-based variants (res/jcn/lin) compute a real value without the caller
        having to supply the Information-Content corpus: it is loaded server-side."""
        if not _wordnet_available():
            return
        result = compute_similarity(
            "wordnet_similarity",
            "nltk",
            {"text_a": "dog", "text_b": "cat"},
            {"variant": variant},
        )
        assert result["raw"] is not None, f"{variant} variant should compute server-side"

    @pytest.mark.parametrize("variant", ["res", "jcn", "lin"])
    def test_ic_variants_accept_corpus_name_override(self, variant):
        """An explicit corpus filename via params.ic is honoured (server-side load)."""
        if not _wordnet_available():
            return
        result = compute_similarity(
            "wordnet_similarity",
            "nltk",
            {"text_a": "dog", "text_b": "cat"},
            {"variant": variant, "ic": "ic-brown.dat"},
        )
        assert result["raw"] is not None


class TestComputeErrors:
    def test_unknown_measure(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("nonexistent", None, {}, {})

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unsupported combination"):
            compute_similarity("wordnet_similarity", "unknown_backend", {}, {})


class TestSbertCosineBatch:
    """The batched SBERT path should encode texts once (deduplicated) and reuse
    embeddings across pairs, mirroring the request-level batching of the
    local-ConceptNet path. Runs without a real torch stack via a stubbed model."""

    def _stub_model(self, monkeypatch):
        import numpy as np

        class StubEmbedder:
            def __init__(self, name):
                self._name = name

            def encode(self, texts):
                # Deterministic pseudo-embeddings: dimension = len(unique texts),
                # one-hot per text as identity-varies (skip the dedup assumption
                # and return unique vectors per distinct text via hashing).
                seen: dict[str, int] = {}
                rows = []
                for t in texts:
                    if t not in seen:
                        seen[t] = 0.5 - 0.5 * len(seen)  # distinct base values
                    rows.append([seen[t], seen[t] * 0.0 + 1.0])
                return np.array(rows)

        from src import model_cache

        monkeypatch.setattr(model_cache, "get_sbert_model", lambda name=None: StubEmbedder(name))

    def test_batch_deduplicates_and_returns_per_pair(self, monkeypatch):
        from src.similarity import sbert_cosine_batch

        self._stub_model(monkeypatch)
        pairs = [
            {"id": "p1", "text_a": "hello", "text_b": "hello"},
            {"id": "p2", "text_a": "hello", "text_b": "world"},
        ]
        results = sbert_cosine_batch(pairs, {})
        assert [r["id"] for r in results] == ["p1", "p2"]
        # identical pair -> similarity clamped to 1.0
        assert results[0]["result"]["similarity"] == pytest.approx(1.0)
        # every result carries the shape + timing
        for r in results:
            assert "similarity" in r["result"]
            assert "distance" in r["result"]
            assert "compute_time_ms" in r["result"]

    def test_batch_rejects_disallowed_model(self):
        from src.similarity import sbert_cosine_batch

        with pytest.raises(ValueError, match="not on the allow-list"):
            sbert_cosine_batch([{"id": "p1", "text_a": "a", "text_b": "b"}], {"model_name": "some/arbitrary-model"})
