"""Similarity computation implementations for Tier 1 (Spec A).

Each function takes input dict and params dict, returns a result dict
with 'raw', 'similarity' (normalized to [0,1]), and 'distance' keys.
"""

import math
import time
from typing import Any


def _normalize_similarity(raw: float, measure: str, backend: str, **kwargs) -> dict[str, Any]:
    """Normalize raw output to similarity [0,1] and distance.

    Returns dict with raw, similarity, distance keys.
    """
    result: dict[str, Any] = {"raw": raw}

    # Measures that are already similarity in [0,1]
    if measure in ("jaro_winkler", "lcs") and backend == "rapidfuzz":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "token_set" and backend == "nltk":
        # NLTK returns distance (0 = identical)
        result["distance"] = raw
        result["similarity"] = 1.0 - raw
    elif measure == "token_set" and backend == "textdistance":
        # textdistance token algorithms return similarity in [0,1]
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "sequence_alignment" and backend == "textdistance":
        result["distance"] = raw
        result["similarity"] = 1.0 / (1.0 + raw) if raw >= 0 else 0.0
    elif measure == "compression_ncd" and backend == "textdistance":
        result["distance"] = raw
        result["similarity"] = 1.0 - raw
    elif measure == "phonetic" and backend == "textdistance":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "tfidf_cosine" and backend == "sklearn":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif backend == "textdistance" and measure in ("levenshtein", "damerau_levenshtein", "hamming"):
        # textdistance distance functions return int distance
        result["distance"] = raw
        result["similarity"] = 1.0 / (1.0 + raw) if raw >= 0 else 0.0
    elif backend == "textdistance" and measure in ("jaro_winkler", "lcs"):
        # textdistance similarity functions return float in [0,1]
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "embedding_cosine" and backend == "gensim":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "sbert_cosine" and backend == "sentence_transformers":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "cross_encoder" and backend == "sentence_transformers":
        result["similarity"] = raw
        result["distance"] = 1.0 - raw
    elif measure == "wordnet_similarity" and backend == "nltk":
        # WordNet path/wup are [0,1], lch is unbounded
        result["similarity"] = raw
        result["distance"] = 1.0 - min(raw, 1.0) if raw <= 1.0 else 0.0
    elif measure == "wmd" and backend == "gensim":
        # WMD returns distance (lower = more similar)
        result["distance"] = raw
        # Normalize: exp(-distance) maps [0,inf) to (0,1]
        result["similarity"] = math.exp(-raw)
    else:
        # Default: treat as distance, invert
        result["distance"] = raw
        result["similarity"] = 1.0 / (1.0 + raw) if raw >= 0 else 0.0

    return result


# ─── Levenshtein ──────────────────────────────────────────────────────────────


def _levenshtein_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.metrics.distance import edit_distance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    substitution_cost = params.get("substitution_cost", 1)
    transpositions = params.get("transpositions", False)
    raw = edit_distance(a, b, substitution_cost=substitution_cost, transpositions=transpositions)
    return _normalize_similarity(raw, "levenshtein", "nltk")


def _levenshtein_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz.distance import Levenshtein

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    weights = params.get("weights")
    score_cutoff = params.get("score_cutoff")
    raw = Levenshtein.distance(a, b, weights=weights, score_cutoff=score_cutoff)
    return _normalize_similarity(raw, "levenshtein", "rapidfuzz")


# ─── Damerau-Levenshtein ──────────────────────────────────────────────────────


def _damerau_levenshtein_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.metrics.distance import edit_distance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    substitution_cost = params.get("substitution_cost", 1)
    raw = edit_distance(a, b, substitution_cost=substitution_cost, transpositions=True)
    return _normalize_similarity(raw, "levenshtein", "nltk")


def _damerau_levenshtein_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz.distance import DamerauLevenshtein

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    score_cutoff = params.get("score_cutoff")
    raw = DamerauLevenshtein.distance(a, b, score_cutoff=score_cutoff)
    return _normalize_similarity(raw, "levenshtein", "rapidfuzz")


# ─── Jaro-Winkler ─────────────────────────────────────────────────────────────


def _jaro_winkler_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz.distance import Jaro, JaroWinkler

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "jaro_winkler")
    if variant == "jaro":
        raw = Jaro.similarity(a, b)
    else:
        prefix_weight = params.get("prefix_weight", 0.1)
        raw = JaroWinkler.similarity(a, b, prefix_weight=prefix_weight)
    return _normalize_similarity(raw, "jaro_winkler", "rapidfuzz")


# ─── Hamming ──────────────────────────────────────────────────────────────────


def _hamming_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz.distance import Hamming

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    pad = params.get("pad", True)
    raw = Hamming.distance(a, b, pad=pad)
    return _normalize_similarity(raw, "levenshtein", "rapidfuzz")


# ─── LCS ──────────────────────────────────────────────────────────────────────


def _lcs_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz.distance import LCSseq

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "subsequence")
    if variant == "indel":
        from rapidfuzz.distance import Indel

        raw = Indel.normalized_similarity(a, b)
    else:
        raw = LCSseq.normalized_similarity(a, b)
    return _normalize_similarity(raw, "lcs", "rapidfuzz")


# ─── Token-set ────────────────────────────────────────────────────────────────


def _token_set_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.metrics.distance import binary_distance, jaccard_distance, masi_distance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "jaccard")
    set_a = frozenset(a.split())
    set_b = frozenset(b.split())
    if variant == "masi":
        raw = masi_distance(set_a, set_b)
    elif variant == "binary":
        raw = binary_distance(set_a, set_b)
    else:
        raw = jaccard_distance(set_a, set_b)
    return _normalize_similarity(raw, "token_set", "nltk")


# ─── Embedding cosine (gensim) ────────────────────────────────────────────────


def _embedding_cosine_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_gensim_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "glove-wiki-gigaword-50")
    kv = get_gensim_model(model_name)

    # Try word-level first, fall back to n_similarity for multi-word
    words_a = a.split()
    words_b = b.split()
    if len(words_a) == 1 and len(words_b) == 1:
        raw = float(kv.similarity(words_a[0], words_b[0]))
    else:
        raw = float(kv.n_similarity(words_a, words_b))
    return _normalize_similarity(raw, "embedding_cosine", "gensim")


# ─── SBERT cosine ─────────────────────────────────────────────────────────────


def _sbert_cosine(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_sbert_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    model = get_sbert_model(model_name)
    emb = model.encode([a, b])
    from sentence_transformers import util

    sim = float(util.cos_sim(emb[0], emb[1])[0][0])
    return _normalize_similarity(sim, "sbert_cosine", "sentence_transformers")


# ─── WMD ──────────────────────────────────────────────────────────────────────


def _wmd_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_gensim_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "glove-wiki-gigaword-50")
    kv = get_gensim_model(model_name)
    raw = float(kv.wmdistance(a.split(), b.split()))
    return _normalize_similarity(raw, "wmd", "gensim")


# ─── Cross-encoder ────────────────────────────────────────────────────────────


def _cross_encoder(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_cross_encoder_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "cross-encoder/stsb-roberta-base")
    model = get_cross_encoder_model(model_name)
    raw = float(model.predict([(a, b)])[0])
    return _normalize_similarity(raw, "cross_encoder", "sentence_transformers")


# ─── WordNet similarity ───────────────────────────────────────────────────────


def _wordnet_similarity_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "path")

    synsets_a = wn.synsets(a)
    synsets_b = wn.synsets(b)
    if not synsets_a or not synsets_b:
        return {"raw": None, "similarity": None, "distance": None, "error": f"No synsets found for '{a}' or '{b}'"}

    best = -1.0
    for sa in synsets_a:
        for sb in synsets_b:
            if variant == "wup":
                try:
                    val = sa.wup_similarity(sb)
                except Exception:  # noqa: BLE001
                    val = None
            elif variant == "lch":
                try:
                    val = sa.lch_similarity(sb)
                except Exception:  # noqa: BLE001
                    val = None
            elif variant == "res":
                ic = params.get("ic")
                if ic is None:
                    raise ValueError("Information Content corpus required for 'res' variant. Use nltk.download('wordnet_ic')")
                try:
                    val = sa.res_similarity(sb, ic)
                except Exception:  # noqa: BLE001
                    val = None
            elif variant == "jcn":
                ic = params.get("ic")
                if ic is None:
                    raise ValueError("Information Content corpus required for 'jcn' variant. Use nltk.download('wordnet_ic')")
                try:
                    val = sa.jcn_similarity(sb, ic)
                except Exception:  # noqa: BLE001
                    val = None
            elif variant == "lin":
                ic = params.get("ic")
                if ic is None:
                    raise ValueError("Information Content corpus required for 'lin' variant. Use nltk.download('wordnet_ic')")
                try:
                    val = sa.lin_similarity(sb, ic)
                except Exception:  # noqa: BLE001
                    val = None
            else:  # path
                try:
                    val = sa.path_similarity(sb)
                except Exception:  # noqa: BLE001
                    val = None
            if val is not None and val > best:
                best = val

    if best < 0:
        return {"raw": None, "similarity": None, "distance": None, "error": "No similarity could be computed"}

    return _normalize_similarity(best, "wordnet_similarity", "nltk")


# ─── Dispatcher ───────────────────────────────────────────────────────────────

SIMILARITY_DISPATCH: dict[tuple[str, str], Any] = {
    ("levenshtein", "nltk"): _levenshtein_nltk,
    ("levenshtein", "rapidfuzz"): _levenshtein_rapidfuzz,
    ("damerau_levenshtein", "nltk"): _damerau_levenshtein_nltk,
    ("damerau_levenshtein", "rapidfuzz"): _damerau_levenshtein_rapidfuzz,
    ("jaro_winkler", "rapidfuzz"): _jaro_winkler_rapidfuzz,
    ("hamming", "rapidfuzz"): _hamming_rapidfuzz,
    ("lcs", "rapidfuzz"): _lcs_rapidfuzz,
    ("token_set", "nltk"): _token_set_nltk,
    ("embedding_cosine", "gensim"): _embedding_cosine_gensim,
    ("sbert_cosine", "sentence_transformers"): _sbert_cosine,
    ("wmd", "gensim"): _wmd_gensim,
    ("cross_encoder", "sentence_transformers"): _cross_encoder,
    ("wordnet_similarity", "nltk"): _wordnet_similarity_nltk,
}

DEFAULT_BACKENDS: dict[str, str] = {
    "levenshtein": "nltk",
    "damerau_levenshtein": "nltk",
    "jaro_winkler": "rapidfuzz",
    "hamming": "rapidfuzz",
    "lcs": "rapidfuzz",
    "token_set": "nltk",
    "embedding_cosine": "gensim",
    "sbert_cosine": "sentence_transformers",
    "wmd": "gensim",
    "cross_encoder": "sentence_transformers",
    "wordnet_similarity": "nltk",
}


def compute_similarity(measure: str, backend: str | None, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Compute a similarity measure and return the result dict."""
    if backend is None:
        backend = DEFAULT_BACKENDS.get(measure, "nltk")

    key = (measure, backend)
    func = SIMILARITY_DISPATCH.get(key)
    if func is None:
        raise ValueError(f"Unsupported combination: measure={measure}, backend={backend}")

    start = time.monotonic()
    result = func(input_data, params)
    elapsed = time.monotonic() - start
    result["compute_time_ms"] = round(elapsed * 1000, 2)
    return result


# ─── Spec B / Spec C extension registration ──────────────────────────────────
# Imported at the bottom to avoid circular imports: the extension modules
# mutate SIMILARITY_DISPATCH / DEFAULT_BACKENDS, which must exist first.
# Importing here ensures `from src.similarity import compute_similarity` always
# sees the full catalog regardless of what the caller imports.

try:
    from . import (
        similarity_spec_b,  # noqa: F401
        similarity_spec_c,  # noqa: F401
    )
except ImportError:  # pragma: no cover
    # similarity_spec_c may not exist until Phase 4/5; don't fail on import
    try:
        from . import similarity_spec_b  # noqa: F401
    except ImportError:  # pragma: no cover
        pass
