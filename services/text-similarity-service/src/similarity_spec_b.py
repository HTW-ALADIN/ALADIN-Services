"""Spec B similarity measures — textdistance and scikit-learn additions.

Adds these 4 new tags (additive, does not touch Tier-1 tags):
- sequence_alignment (textdistance.needleman_wunsch/gotoh/smith_waterman)
- compression_ncd (textdistance entropy_ncd and NCD variants)
- phonetic (textdistance.editex / MRA)
- tfidf_cosine (sklearn TfidfVectorizer + cosine_similarity)
"""

from typing import Any

from .similarity import DEFAULT_BACKENDS, SIMILARITY_DISPATCH, _normalize_similarity

# ─── Sequence alignment ───────────────────────────────────────────────────────


def _sequence_alignment_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "needleman_wunsch")

    if variant == "needleman_wunsch":
        alg = textdistance.needleman_wunsch
        raw = alg.distance(a, b)
    elif variant == "smith_waterman":
        alg = textdistance.smith_waterman
        raw = alg.distance(a, b)
    elif variant == "gotoh":
        alg = textdistance.gotoh
        raw = alg.distance(a, b)
    else:
        raise ValueError(f"Unknown sequence_alignment variant: {variant}")

    return _normalize_similarity(raw, "sequence_alignment", "textdistance")


# ─── Compression NCD ──────────────────────────────────────────────────────────


def _compression_ncd_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "entropy")

    if variant == "entropy":
        raw = textdistance.entropy_ncd(a, b)
    elif variant == "arithmetic":
        raw = textdistance.arith_ncd(a, b)
    elif variant == "rle":
        raw = textdistance.rle_ncd(a, b)
    elif variant == "bwt_rle":
        raw = textdistance.bwt_rle_ncd(a, b)
    elif variant == "sqrt":
        raw = textdistance.sqrt_ncd(a, b)
    else:
        raise ValueError(f"Unknown compression_ncd variant: {variant}")

    return _normalize_similarity(raw, "compression_ncd", "textdistance")


# ─── Phonetic ─────────────────────────────────────────────────────────────────


def _phonetic_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "editex")

    if variant == "editex":
        raw = textdistance.editex.normalized_similarity(a, b)
    elif variant == "mra":
        raw = textdistance.mra.normalized_similarity(a, b)
    else:
        raise ValueError(f"Unknown phonetic variant: {variant}")

    return _normalize_similarity(raw, "phonetic", "textdistance")


# ─── TF-IDF cosine ────────────────────────────────────────────────────────────


def _tfidf_cosine_sklearn(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    max_features = params.get("max_features")
    ngram_range = params.get("ngram_range", (1, 1))

    docs = [a, b]
    vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=tuple(ngram_range))
    tfidf = vectorizer.fit_transform(docs)
    sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
    return _normalize_similarity(sim, "tfidf_cosine", "sklearn")


# ─── Textdistance backends for existing Tier-1 tags (Spec B §5.2) ───────────


def _levenshtein_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    raw = textdistance.levenshtein.distance(a, b)
    return _normalize_similarity(raw, "levenshtein", "textdistance")


def _damerau_levenshtein_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    raw = textdistance.damerau_levenshtein.distance(a, b)
    return _normalize_similarity(raw, "levenshtein", "textdistance")


def _jaro_winkler_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "jaro_winkler")
    if variant == "jaro":
        raw = textdistance.jaro.normalized_similarity(a, b)
    else:
        raw = textdistance.jaro_winkler.normalized_similarity(a, b)
    return _normalize_similarity(raw, "jaro_winkler", "textdistance")


def _hamming_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    raw = textdistance.hamming.distance(a, b)
    return _normalize_similarity(raw, "levenshtein", "textdistance")


def _lcs_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "subsequence")
    if variant == "ratcliff_obershelp":
        raw = textdistance.ratcliff_obershelp.normalized_similarity(a, b)
    else:
        raw = textdistance.lcsseq.normalized_similarity(a, b)
    return _normalize_similarity(raw, "lcs", "textdistance")


def _token_set_textdistance(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import textdistance

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "jaccard")

    def _tokens(s: str):
        return s.split()

    if variant == "jaccard":
        raw = textdistance.jaccard(_tokens(a), _tokens(b))
    elif variant == "sorensen_dice":
        raw = textdistance.sorensen_dice(_tokens(a), _tokens(b))
    elif variant == "tversky":
        alpha = params.get("alpha", 1.0)
        beta = params.get("beta", 1.0)
        raw = textdistance.tversky(_tokens(a), _tokens(b), alpha=alpha, beta=beta)
    elif variant == "overlap":
        raw = textdistance.overlap(_tokens(a), _tokens(b))
    elif variant == "cosine":
        raw = textdistance.cosine(_tokens(a), _tokens(b))
    elif variant == "monge_elkan":
        raw = textdistance.monge_elkan(_tokens(a), _tokens(b))
    elif variant == "bag":
        raw = textdistance.bag(_tokens(a), _tokens(b))
    else:
        raise ValueError(f"Unknown token_set variant: {variant}")

    # textdistance token algorithms return similarity in [0,1]
    return _normalize_similarity(raw, "token_set", "textdistance")


# ─── Register in dispatchers ─────────────────────────────────────────────────

SIMILARITY_DISPATCH.update(
    {
        ("sequence_alignment", "textdistance"): _sequence_alignment_textdistance,
        ("compression_ncd", "textdistance"): _compression_ncd_textdistance,
        ("phonetic", "textdistance"): _phonetic_textdistance,
        ("tfidf_cosine", "sklearn"): _tfidf_cosine_sklearn,
        # Backend extensions on existing tags (Spec B §5.2)
        ("levenshtein", "textdistance"): _levenshtein_textdistance,
        ("damerau_levenshtein", "textdistance"): _damerau_levenshtein_textdistance,
        ("jaro_winkler", "textdistance"): _jaro_winkler_textdistance,
        ("hamming", "textdistance"): _hamming_textdistance,
        ("lcs", "textdistance"): _lcs_textdistance,
        ("token_set", "textdistance"): _token_set_textdistance,
    }
)

DEFAULT_BACKENDS.update(
    {
        "sequence_alignment": "textdistance",
        "compression_ncd": "textdistance",
        "phonetic": "textdistance",
        "tfidf_cosine": "sklearn",
    }
)
