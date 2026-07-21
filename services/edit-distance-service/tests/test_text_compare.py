"""Unit tests for text edit distance computation.

Tests each algorithm/backend combination with concrete value assertions.
Duplicates across backends are intentional: they verify cross-backend
consistency for the same canonical family.
"""

import pytest
from src.text import compute_text
from src.models import InputPair, InputPhonetic


class TestLevenshtein:
    """Levenshtein distance — all 4 backends should agree."""

    def test_rapidfuzz(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("levenshtein", "rapidfuzz", inputs, {})
        assert result_type == "scalar_distance"
        assert results[0].value == 3

    def test_textdistance(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("levenshtein", "textdistance", inputs, {})
        assert results[0].value == 3

    def test_jellyfish(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("levenshtein", "jellyfish", inputs, {})
        assert results[0].value == 3

    def test_edlib(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("levenshtein", "edlib", inputs, {})
        assert results[0].value == 3


class TestDamerauLevenshtein:
    def test_rapidfuzz(self):
        inputs = [InputPair(id="p1", a="jellyfish", b="jellyfihs")]
        results, _, _ = compute_text("damerau_levenshtein", "rapidfuzz", inputs, {})
        assert results[0].value == 1

    def test_textdistance(self):
        inputs = [InputPair(id="p1", a="jellyfish", b="jellyfihs")]
        results, _, _ = compute_text("damerau_levenshtein", "textdistance", inputs, {})
        assert results[0].value == 1

    def test_jellyfish(self):
        inputs = [InputPair(id="p1", a="jellyfish", b="jellyfihs")]
        results, _, _ = compute_text("damerau_levenshtein", "jellyfish", inputs, {})
        assert results[0].value == 1


class TestHamming:
    def test_rapidfuzz(self):
        inputs = [InputPair(id="p1", a="karolin", b="kathrin")]
        results, _, _ = compute_text("hamming", "rapidfuzz", inputs, {})
        assert results[0].value == 3

    def test_textdistance(self):
        inputs = [InputPair(id="p1", a="karolin", b="kathrin")]
        results, _, _ = compute_text("hamming", "textdistance", inputs, {})
        assert results[0].value == 3

    def test_jellyfish(self):
        inputs = [InputPair(id="p1", a="karolin", b="kathrin")]
        results, _, _ = compute_text("hamming", "jellyfish", inputs, {})
        assert results[0].value == 3


class TestJaroWinkler:
    """Jaro-Winkler similarity — all 3 backends should agree on MARTHA/MARHTA."""

    def test_rapidfuzz(self):
        inputs = [InputPair(id="p1", a="MARTHA", b="MARHTA")]
        results, _, _ = compute_text("jaro_winkler", "rapidfuzz", inputs, {})
        # JaroWinkler.similarity(MARTHA, MARHTA) = 0.9611...
        assert results[0].value == pytest.approx(0.961, abs=0.01)

    def test_textdistance(self):
        inputs = [InputPair(id="p1", a="MARTHA", b="MARHTA")]
        results, _, _ = compute_text("jaro_winkler", "textdistance", inputs, {})
        assert results[0].value == pytest.approx(0.961, abs=0.01)

    def test_jellyfish(self):
        inputs = [InputPair(id="p1", a="MARTHA", b="MARHTA")]
        results, _, _ = compute_text("jaro_winkler", "jellyfish", inputs, {})
        assert results[0].value == pytest.approx(0.961, abs=0.01)


class TestOsa:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="ca", b="abc")]
        results, result_type, _ = compute_text("osa", "rapidfuzz", inputs, {})
        assert result_type == "scalar_distance"
        assert results[0].value >= 0


class TestIndel:
    """Insertion/deletion-only distance (no substitution weight).
    Both backends should agree on the same value."""

    def test_rapidfuzz(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("indel", "rapidfuzz", inputs, {})
        # Indel counts substitutions as delete+insert: kitten→sitting
        # k→s (del+ins=2), e→i (del+ins=2), +g (ins=1) = 5
        assert results[0].value == 5

    def test_textdistance(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("indel", "textdistance", inputs, {})
        assert results[0].value == 5

    def test_backends_agree(self):
        pairs = [InputPair(id="p1", a="kitten", b="sitting"), InputPair(id="p2", a="flaw", b="lawn")]
        r1, _, _ = compute_text("indel", "rapidfuzz", pairs, {})
        r2, _, _ = compute_text("indel", "textdistance", pairs, {})
        assert r1[0].value == r2[0].value
        assert r1[1].value == r2[1].value


class TestLcs:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("lcs", "textdistance", inputs, {})
        assert result_type == "sequence"
        assert len(results[0].value) > 0


class TestNeedlemanWunsch:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("needleman_wunsch", "textdistance", inputs, {"gap_cost": 1.0})
        assert result_type == "alignment"


class TestGotoh:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("gotoh", "textdistance", inputs, {})
        assert result_type == "scalar_distance"
        assert results[0].value >= 0


class TestSmithWaterman:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("smith_waterman", "textdistance", inputs, {})
        assert result_type == "scalar_distance"
        assert results[0].value >= 0


class TestTokenSetSimilarity:
    def test_jaccard(self):
        inputs = [InputPair(id="p1", a="hello world", b="world hello")]
        results, _, _ = compute_text("token_set_similarity", "textdistance", inputs, {"metric": "jaccard"})
        assert results[0].value > 0


class TestNcd:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, _, _ = compute_text("ncd", "textdistance", inputs, {"qval": 1, "compressor": "zlib"})
        assert results[0].value >= 0


class TestPhoneticEncoding:
    def test_soundex(self):
        inputs = [InputPhonetic(id="w1", text="Jellyfish")]
        results, result_type, _ = compute_text("phonetic_encoding", "jellyfish", inputs, {"scheme": "soundex"})
        assert result_type == "phonetic_code"
        assert "soundex" in results[0].codes


class TestLongSequenceAlignment:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting")]
        results, result_type, _ = compute_text("long_sequence_alignment", "edlib", inputs, {"mode": "NW", "task": "distance"})
        assert result_type == "alignment"
        assert results[0].edit_distance >= 0


class TestDiffPatch:
    def test_basic(self):
        inputs = [InputPair(id="p1", a="The quick brown fox", b="The slow brown fox")]
        results, result_type, _ = compute_text("diff_patch", "diff_match_patch", inputs, {})
        assert result_type == "edit_script"
        assert len(results[0].diffs) > 0


class TestBatch:
    def test_multiple_pairs(self):
        inputs = [InputPair(id="p1", a="kitten", b="sitting"), InputPair(id="p2", a="flaw", b="lawn"), InputPair(id="p3", a="hello", b="world")]
        results, _, _ = compute_text("levenshtein", "rapidfuzz", inputs, {})
        assert len(results) == 3
        assert all(r.id.startswith("p") for r in results)


class TestErrors:
    def test_unknown_algorithm(self):
        inputs = [InputPair(id="p1", a="a", b="b")]
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_text("nonexistent", "rapidfuzz", inputs, {})

    def test_unknown_backend(self):
        inputs = [InputPair(id="p1", a="a", b="b")]
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_text("levenshtein", "nonexistent", inputs, {})
