"""Text edit distance implementations using RapidFuzz, textdistance, jellyfish, edlib, and diff-match-patch."""

import time
from typing import Any

from ..models import (
    AlignmentResult,
    EditScriptResult,
    InputPair,
    InputPhonetic,
    PhoneticCodeResult,
    ScalarDistanceResult,
    SequenceResult,
)

# ─── RapidFuzz Backend ────────────────────────────────────────────────────────

def _rapidfuzz_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import Levenshtein
    weights = tuple(params.get("weights")) if params.get("weights") else None
    d = Levenshtein.distance(
        pair.a, pair.b,
        weights=weights,
        processor=params.get("processor"),
        score_cutoff=params.get("score_cutoff"),
    )
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _rapidfuzz_damerau_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import DamerauLevenshtein
    d = DamerauLevenshtein.distance(
        pair.a, pair.b,
        processor=params.get("processor"),
        score_cutoff=params.get("score_cutoff"),
    )
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _rapidfuzz_hamming(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import Hamming
    d = Hamming.distance(
        pair.a, pair.b,
        pad=params.get("pad"),
        processor=params.get("processor"),
        score_cutoff=params.get("score_cutoff"),
    )
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _rapidfuzz_jaro_winkler(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import JaroWinkler, Jaro
    variant = params.get("variant", "jaro_winkler")
    prefix_weight = params.get("prefix_weight", 0.1)
    if variant == "jaro_winkler":
        s = JaroWinkler.similarity(pair.a, pair.b, prefix_weight=prefix_weight)
    else:
        d = Jaro.similarity(pair.a, pair.b)
        s = d
    return ScalarDistanceResult(id=pair.id, value=s, normalized=s)


def _rapidfuzz_osa(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import OSA
    d = OSA.distance(
        pair.a, pair.b,
        processor=params.get("processor"),
        score_cutoff=params.get("score_cutoff"),
    )
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _rapidfuzz_indel(pair: InputPair, params: dict) -> ScalarDistanceResult:
    from rapidfuzz.distance import Indel
    d = Indel.distance(
        pair.a, pair.b,
        processor=params.get("processor"),
        score_cutoff=params.get("score_cutoff"),
    )
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


# ─── textdistance Backend ─────────────────────────────────────────────────────

def _textdistance_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    qval = params.get("qval", 1)
    alg = textdistance.Levenshtein(qval=qval)
    d = alg(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_damerau_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    qval = params.get("qval", 1)
    alg = textdistance.DamerauLevenshtein(qval=qval)
    d = alg(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_hamming(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    qval = params.get("qval", 1)
    alg = textdistance.Hamming(qval=qval)
    d = alg(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_jaro_winkler(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    variant = params.get("variant", "jaro_winkler")
    if variant == "jaro_winkler":
        s = textdistance.jaro_winkler(pair.a, pair.b)
    else:
        s = textdistance.jaro(pair.a, pair.b)
    return ScalarDistanceResult(id=pair.id, value=s, normalized=s)


def _textdistance_indel(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    # LCSSeq-based distance = len(a) + len(b) - 2 * len(LCS(a,b))
    lcs = textdistance.LCSSeq()(pair.a, pair.b)
    d = len(pair.a) + len(pair.b) - 2 * len(lcs)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_lcs(pair: InputPair, params: dict) -> SequenceResult:
    import textdistance
    lcs_str = textdistance.lcsseq(pair.a, pair.b)
    return SequenceResult(id=pair.id, value=lcs_str, length=len(lcs_str))


def _textdistance_needleman_wunsch(pair: InputPair, params: dict) -> AlignmentResult:
    import textdistance
    # NeedlemanWunsch is a class in textdistance, call it as a function
    d = textdistance.needleman_wunsch(pair.a, pair.b)
    return AlignmentResult(id=pair.id, edit_distance=int(d), cigar=None)


def _textdistance_gotoh(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    d = textdistance.gotoh(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_smith_waterman(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    d = textdistance.smith_waterman(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _textdistance_token_set(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    metric = params.get("metric", "jaccard")
    alg = {
        "jaccard": textdistance.Jaccard,
        "sorensen": textdistance.Sorensen,
        "tversky": textdistance.Tversky,
        "cosine": textdistance.Cosine,
    }.get(metric, textdistance.Jaccard)(qval=params.get("qval", 1))
    s = alg(pair.a, pair.b)
    return ScalarDistanceResult(id=pair.id, value=s, normalized=s)


def _textdistance_ncd(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import textdistance
    compressor = params.get("compressor", "zlib")
    alg_map = {
        "zlib": textdistance.ZLIBNCD,
        "bzip2": textdistance.BZ2NCD,
        "lzma": textdistance.LZMANCD,
    }
    cls = alg_map.get(compressor, textdistance.ZLIBNCD)
    alg = cls()
    d = alg(pair.a, pair.b)
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d)


# ─── jellyfish Backend ───────────────────────────────────────────────────────

def _jellyfish_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import jellyfish
    d = jellyfish.levenshtein_distance(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _jellyfish_damerau_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import jellyfish
    d = jellyfish.damerau_levenshtein_distance(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _jellyfish_hamming(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import jellyfish
    d = jellyfish.hamming_distance(pair.a, pair.b)
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _jellyfish_jaro_winkler(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import jellyfish
    variant = params.get("variant", "jaro_winkler")
    long_tolerance = params.get("long_tolerance", False)
    if variant == "jaro_winkler":
        s = jellyfish.jaro_winkler_similarity(pair.a, pair.b, long_tolerance=long_tolerance)
    else:
        s = jellyfish.jaro_similarity(pair.a, pair.b)
    return ScalarDistanceResult(id=pair.id, value=s, normalized=s)


# ─── jellyfish Phonetic Encoding ─────────────────────────────────────────────

def _jellyfish_phonetic(input_item: InputPhonetic, params: dict) -> PhoneticCodeResult:
    import jellyfish
    scheme = params.get("scheme", "soundex")
    text = input_item.text
    fn = {
        "soundex": jellyfish.soundex,
        "metaphone": jellyfish.metaphone,
        "nysiis": jellyfish.nysiis,
    }.get(scheme)
    if fn is None:
        raise ValueError(f"Unknown phonetic scheme: {scheme}")
    return PhoneticCodeResult(id=input_item.id, codes={scheme: fn(text)})


# ─── edlib Backend ───────────────────────────────────────────────────────────

def _edlib_levenshtein(pair: InputPair, params: dict) -> ScalarDistanceResult:
    import edlib
    result = edlib.align(pair.a, pair.b, mode="NW", task="distance")
    d = result["editDistance"]
    max_len = max(len(pair.a), len(pair.b))
    return ScalarDistanceResult(id=pair.id, value=d, normalized=d / max_len if max_len > 0 else 0.0)


def _edlib_long_sequence_alignment(pair: InputPair, params: dict) -> AlignmentResult:
    import edlib
    mode = params.get("mode", "NW")
    task = params.get("task", "distance")
    k = params.get("k")
    additional_equalites = params.get("additional_equalites")

    kwargs = {"mode": mode, "task": task}
    if k is not None:
        kwargs["k"] = k
    if additional_equalites:
        kwargs["additionalEqualities"] = additional_equalites

    result = edlib.align(pair.a, pair.b, **kwargs)

    return AlignmentResult(
        id=pair.id,
        edit_distance=result.get("editDistance", -1),
        locations=result.get("locations"),
        cigar=result.get("cigar"),
    )


# ─── diff-match-patch Backend ────────────────────────────────────────────────

def _diff_match_patch_diff(pair: InputPair, params: dict) -> EditScriptResult:
    from diff_match_patch import diff_match_patch
    dmp = diff_match_patch()
    checklines = params.get("checklines", True)
    deadline = params.get("deadline", None)
    diffs = dmp.diff_main(pair.a, pair.b, checklines=checklines, deadline=deadline)
    dmp.diff_cleanupSemantic(diffs)
    lev = dmp.diff_levenshtein(diffs)
    serialized = [[op, text] for op, text in diffs]
    return EditScriptResult(id=pair.id, diffs=serialized, levenshtein=lev)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

BACKEND_DISPATCH = {
    ("levenshtein", "rapidfuzz"): _rapidfuzz_levenshtein,
    ("levenshtein", "textdistance"): _textdistance_levenshtein,
    ("levenshtein", "jellyfish"): _jellyfish_levenshtein,
    ("levenshtein", "edlib"): _edlib_levenshtein,
    ("damerau_levenshtein", "rapidfuzz"): _rapidfuzz_damerau_levenshtein,
    ("damerau_levenshtein", "textdistance"): _textdistance_damerau_levenshtein,
    ("damerau_levenshtein", "jellyfish"): _jellyfish_damerau_levenshtein,
    ("hamming", "rapidfuzz"): _rapidfuzz_hamming,
    ("hamming", "textdistance"): _textdistance_hamming,
    ("hamming", "jellyfish"): _jellyfish_hamming,
    ("jaro_winkler", "rapidfuzz"): _rapidfuzz_jaro_winkler,
    ("jaro_winkler", "textdistance"): _textdistance_jaro_winkler,
    ("jaro_winkler", "jellyfish"): _jellyfish_jaro_winkler,
    ("osa", "rapidfuzz"): _rapidfuzz_osa,
    ("indel", "rapidfuzz"): _rapidfuzz_indel,
    ("indel", "textdistance"): _textdistance_indel,
    ("lcs", "textdistance"): _textdistance_lcs,
    ("needleman_wunsch", "textdistance"): _textdistance_needleman_wunsch,
    ("gotoh", "textdistance"): _textdistance_gotoh,
    ("smith_waterman", "textdistance"): _textdistance_smith_waterman,
    ("token_set_similarity", "textdistance"): _textdistance_token_set,
    ("ncd", "textdistance"): _textdistance_ncd,
    ("long_sequence_alignment", "edlib"): _edlib_long_sequence_alignment,
    ("diff_patch", "diff_match_patch"): _diff_match_patch_diff,
    ("phonetic_encoding", "jellyfish"): _jellyfish_phonetic,
}


def compute_text(algorithm: str, backend: str, inputs: list[InputPair] | list[InputPhonetic], params: dict) -> tuple[list[Any], str]:
    """Compute text edit distance for a batch of inputs.

    Returns (results, result_type).
    """
    key = (algorithm, backend)
    if key not in BACKEND_DISPATCH:
        raise ValueError(f"Unsupported algorithm/backend combination: {algorithm}/{backend}")

    func = BACKEND_DISPATCH[key]
    t0 = time.perf_counter()
    results = [func(inp, params) for inp in inputs]
    elapsed = (time.perf_counter() - t0) * 1000

    # Determine result type from first result
    result_type = type(results[0]).__name__.replace("Result", "")
    # Map camelCase to snake_case
    type_map = {
        "ScalarDistance": "scalar_distance",
        "Sequence": "sequence",
        "PhoneticCode": "phonetic_code",
        "EditScript": "edit_script",
        "Alignment": "alignment",
    }
    result_type = type_map.get(result_type, "scalar_distance")

    return results, result_type, elapsed


ALGORITHM_CATALOG = [
    {"algorithm": "levenshtein", "backend": "rapidfuzz", "families": ["Levenshtein distance"], "result_type": "scalar_distance", "description": "Levenshtein edit distance (RapidFuzz C++ backend)"},
    {"algorithm": "levenshtein", "backend": "textdistance", "families": ["Levenshtein distance"], "result_type": "scalar_distance", "description": "Levenshtein edit distance (textdistance pure Python)"},
    {"algorithm": "levenshtein", "backend": "jellyfish", "families": ["Levenshtein distance"], "result_type": "scalar_distance", "description": "Levenshtein edit distance (jellyfish Rust core)"},
    {"algorithm": "levenshtein", "backend": "edlib", "families": ["Levenshtein distance", "Long-sequence banded alignment"], "result_type": "scalar_distance", "description": "Levenshtein distance via edlib (banded NW, for long sequences)"},
    {"algorithm": "damerau_levenshtein", "backend": "rapidfuzz", "families": ["Damerau-Levenshtein distance"], "result_type": "scalar_distance", "description": "Damerau-Levenshtein distance (transposition-aware, RapidFuzz)"},
    {"algorithm": "damerau_levenshtein", "backend": "textdistance", "families": ["Damerau-Levenshtein distance"], "result_type": "scalar_distance", "description": "Damerau-Levenshtein distance (textdistance)"},
    {"algorithm": "damerau_levenshtein", "backend": "jellyfish", "families": ["Damerau-Levenshtein distance"], "result_type": "scalar_distance", "description": "Damerau-Levenshtein distance (jellyfish)"},
    {"algorithm": "hamming", "backend": "rapidfuzz", "families": ["Hamming distance"], "result_type": "scalar_distance", "description": "Hamming distance (RapidFuzz)"},
    {"algorithm": "hamming", "backend": "textdistance", "families": ["Hamming distance"], "result_type": "scalar_distance", "description": "Hamming distance (textdistance)"},
    {"algorithm": "hamming", "backend": "jellyfish", "families": ["Hamming distance"], "result_type": "scalar_distance", "description": "Hamming distance (jellyfish)"},
    {"algorithm": "jaro_winkler", "backend": "rapidfuzz", "families": ["Jaro / Jaro-Winkler similarity"], "result_type": "scalar_distance", "description": "Jaro-Winkler similarity (RapidFuzz)"},
    {"algorithm": "jaro_winkler", "backend": "textdistance", "families": ["Jaro / Jaro-Winkler similarity"], "result_type": "scalar_distance", "description": "Jaro-Winkler similarity (textdistance)"},
    {"algorithm": "jaro_winkler", "backend": "jellyfish", "families": ["Jaro / Jaro-Winkler similarity"], "result_type": "scalar_distance", "description": "Jaro-Winkler similarity (jellyfish)"},
    {"algorithm": "osa", "backend": "rapidfuzz", "families": ["Optimal String Alignment"], "result_type": "scalar_distance", "description": "Optimal String Alignment (RapidFuzz)"},
    {"algorithm": "indel", "backend": "rapidfuzz", "families": ["Indel (LCS-based edit distance)"], "result_type": "scalar_distance", "description": "Indel/LCS-based distance (RapidFuzz)"},
    {"algorithm": "indel", "backend": "textdistance", "families": ["Indel (LCS-based edit distance)"], "result_type": "scalar_distance", "description": "Indel/LCS-based distance (textdistance)"},
    {"algorithm": "lcs", "backend": "textdistance", "families": ["Longest Common Subsequence"], "result_type": "sequence", "description": "Longest Common Subsequence extraction (textdistance)"},
    {"algorithm": "needleman_wunsch", "backend": "textdistance", "families": ["Needleman-Wunsch global alignment"], "result_type": "alignment", "description": "Needleman-Wunsch global alignment (textdistance)"},
    {"algorithm": "gotoh", "backend": "textdistance", "families": ["Gotoh affine-gap alignment"], "result_type": "scalar_distance", "description": "Gotoh affine-gap alignment distance (textdistance)"},
    {"algorithm": "smith_waterman", "backend": "textdistance", "families": ["Smith-Waterman local alignment"], "result_type": "scalar_distance", "description": "Smith-Waterman local alignment (textdistance)"},
    {"algorithm": "token_set_similarity", "backend": "textdistance", "families": ["Token/set similarity (Jaccard, Sørensen-Dice, Tversky, Cosine)"], "result_type": "scalar_distance", "description": "Token/set similarity bundle (textdistance)"},
    {"algorithm": "ncd", "backend": "textdistance", "families": ["Normalized Compression Distance"], "result_type": "scalar_distance", "description": "Normalized Compression Distance (textdistance)"},
    {"algorithm": "phonetic_encoding", "backend": "jellyfish", "families": ["Phonetic encoding + Match Rating Comparison"], "result_type": "phonetic_code", "description": "Phonetic encoding (Soundex, Metaphone, NYSIIS) via jellyfish"},
    {"algorithm": "long_sequence_alignment", "backend": "edlib", "families": ["Long-sequence banded/bit-vector alignment"], "result_type": "alignment", "description": "Banded/bit-vector alignment with CIGAR (edlib)"},
    {"algorithm": "diff_patch", "backend": "diff_match_patch", "families": ["Edit-script / diff (Myers) + patch application"], "result_type": "edit_script", "description": "Myers diff with edit-script output (diff-match-patch)"},
]