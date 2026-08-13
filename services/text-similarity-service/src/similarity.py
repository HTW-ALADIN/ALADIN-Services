"""Similarity measures — one function per (measure, backend).

Each function takes input dict and params dict, returns a result dict
with 'raw', 'similarity' (normalized to [0,1]), and 'distance' keys.
DKPro-sidecar measures (topic_model, structural_stylistic) are routed
externally via dkpro_proxy and have no in-process implementation here.
"""

import math
import time
from typing import Any

# (measure, backend) pairs whose raw output is already a similarity in [0,1].
_SIMILARITY_KEYS = {
    ("jaro_winkler", "rapidfuzz"),
    ("jaro_winkler", "textdistance"),
    ("lcs", "rapidfuzz"),
    ("lcs", "textdistance"),
    ("token_set", "textdistance"),
    ("phonetic", "textdistance"),
    ("tfidf_cosine", "sklearn"),
    ("embedding_cosine", "gensim"),
    ("sbert_cosine", "sentence_transformers"),
    ("cross_encoder", "sentence_transformers"),
    ("wordnet_similarity", "nltk"),
}

# (measure, backend) pairs whose raw output is a distance in [0,1] (invert via 1-x).
_UNIT_DISTANCE_KEYS = {("token_set", "nltk"), ("compression_ncd", "textdistance")}


def _normalize_similarity(raw: float, measure: str, backend: str) -> dict[str, Any]:
    """Normalize raw output to {'raw', 'similarity', 'distance'} with similarity in [0,1]."""
    result: dict[str, Any] = {"raw": raw}
    key = (measure, backend)
    if key in _SIMILARITY_KEYS:
        result["similarity"] = raw
        result["distance"] = 1.0 - min(raw, 1.0) if measure == "wordnet_similarity" else 1.0 - raw
    elif measure == "wmd" and backend == "gensim":
        result["distance"] = raw
        result["similarity"] = math.exp(-raw)
    elif key in _UNIT_DISTANCE_KEYS:
        result["distance"] = raw
        result["similarity"] = 1.0 - raw
    else:
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


# ─── textdistance / scikit-learn ─────────────────────────────────────────────


def _sequence_alignment_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "needleman_wunsch")

    if variant == "needleman_wunsch":
        raw = textdistance.needleman_wunsch.distance(a, b)
    elif variant == "smith_waterman":
        raw = textdistance.smith_waterman.distance(a, b)
    elif variant == "gotoh":
        raw = textdistance.gotoh.distance(a, b)
    else:
        raise ValueError(f"Unknown sequence_alignment variant: {variant}")

    return _normalize_similarity(raw, "sequence_alignment", "textdistance")


def _compression_ncd_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "entropy")
    name = {
        "entropy": "entropy_ncd",
        "arithmetic": "arith_ncd",
        "rle": "rle_ncd",
        "bwt_rle": "bwtrle_ncd",
        "sqrt": "sqrt_ncd",
    }.get(variant)
    if name is None:
        raise ValueError(f"Unknown compression_ncd variant: {variant}")

    return _normalize_similarity(getattr(textdistance, name)(a, b), "compression_ncd", "textdistance")


def _phonetic_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "editex")
    alg = {"editex": textdistance.editex, "mra": textdistance.mra}.get(variant)
    if alg is None:
        raise ValueError(f"Unknown phonetic variant: {variant}")

    return _normalize_similarity(alg.normalized_similarity(a, b), "phonetic", "textdistance")


def _tfidf_cosine_sklearn(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    vectorizer = TfidfVectorizer(
        max_features=params.get("max_features"),
        ngram_range=tuple(params.get("ngram_range", (1, 1))),
    )
    tfidf = vectorizer.fit_transform([a, b])
    sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
    return _normalize_similarity(sim, "tfidf_cosine", "sklearn")


def _levenshtein_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    return _normalize_similarity(textdistance.levenshtein.distance(a, b), "levenshtein", "textdistance")


def _damerau_levenshtein_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    return _normalize_similarity(textdistance.damerau_levenshtein.distance(a, b), "levenshtein", "textdistance")


def _jaro_winkler_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    alg = textdistance.jaro if params.get("variant") == "jaro" else textdistance.jaro_winkler
    return _normalize_similarity(alg.normalized_similarity(a, b), "jaro_winkler", "textdistance")


def _hamming_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    return _normalize_similarity(textdistance.hamming.distance(a, b), "levenshtein", "textdistance")


def _lcs_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    alg = textdistance.ratcliff_obershelp if params.get("variant") == "ratcliff_obershelp" else textdistance.lcsseq
    return _normalize_similarity(alg.normalized_similarity(a, b), "lcs", "textdistance")


def _token_set_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a, b = input_data.get("text_a", "").split(), input_data.get("text_b", "").split()
    variant = params.get("variant", "jaccard")
    if variant == "tversky":
        raw = textdistance.tversky(a, b, alpha=params.get("alpha", 1.0), beta=params.get("beta", 1.0))
    else:
        alg = {
            "jaccard": textdistance.jaccard,
            "sorensen_dice": textdistance.sorensen_dice,
            "overlap": textdistance.overlap,
            "cosine": textdistance.cosine,
            "monge_elkan": textdistance.monge_elkan,
            "bag": textdistance.bag,
        }.get(variant)
        if alg is None:
            raise ValueError(f"Unknown token_set variant: {variant}")
        raw = alg(a, b)

    return _normalize_similarity(raw, "token_set", "textdistance")


# ─── BERTScore ────────────────────────────────────────────────────────────────


def _bertscore(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import bert_score

    P, R, F1 = bert_score.score(
        [input_data.get("text_a", "")],
        [input_data.get("text_b", "")],
        model_type=params.get("model_type"),
        lang=params.get("lang"),
        idf=params.get("idf", False),
        rescale_with_baseline=params.get("rescale_with_baseline", False),
    )
    return {"precision": float(P[0]), "recall": float(R[0]), "f1": float(F1[0])}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

SIMILARITY_DISPATCH: dict[tuple[str, str], Any] = {
    ("levenshtein", "nltk"): _levenshtein_nltk,
    ("levenshtein", "rapidfuzz"): _levenshtein_rapidfuzz,
    ("levenshtein", "textdistance"): _levenshtein_textdistance,
    ("damerau_levenshtein", "nltk"): _damerau_levenshtein_nltk,
    ("damerau_levenshtein", "rapidfuzz"): _damerau_levenshtein_rapidfuzz,
    ("damerau_levenshtein", "textdistance"): _damerau_levenshtein_textdistance,
    ("jaro_winkler", "rapidfuzz"): _jaro_winkler_rapidfuzz,
    ("jaro_winkler", "textdistance"): _jaro_winkler_textdistance,
    ("hamming", "rapidfuzz"): _hamming_rapidfuzz,
    ("hamming", "textdistance"): _hamming_textdistance,
    ("lcs", "rapidfuzz"): _lcs_rapidfuzz,
    ("lcs", "textdistance"): _lcs_textdistance,
    ("token_set", "nltk"): _token_set_nltk,
    ("token_set", "textdistance"): _token_set_textdistance,
    ("embedding_cosine", "gensim"): _embedding_cosine_gensim,
    ("sbert_cosine", "sentence_transformers"): _sbert_cosine,
    ("wmd", "gensim"): _wmd_gensim,
    ("cross_encoder", "sentence_transformers"): _cross_encoder,
    ("wordnet_similarity", "nltk"): _wordnet_similarity_nltk,
    ("sequence_alignment", "textdistance"): _sequence_alignment_textdistance,
    ("compression_ncd", "textdistance"): _compression_ncd_textdistance,
    ("phonetic", "textdistance"): _phonetic_textdistance,
    ("tfidf_cosine", "sklearn"): _tfidf_cosine_sklearn,
    ("bertscore", "bertscore"): _bertscore,
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
    "sequence_alignment": "textdistance",
    "compression_ncd": "textdistance",
    "phonetic": "textdistance",
    "tfidf_cosine": "sklearn",
    "bertscore": "bertscore",
    # DKPro-sidecar measures: known measures, computed externally via dkpro_proxy.
    "topic_model": "dkpro",
    "structural_stylistic": "dkpro",
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
