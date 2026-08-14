"""Similarity measures — one function per (measure, backend).

Each function takes input dict and params dict, returns a result dict
with 'raw', 'similarity' (normalized to [0,1]), and 'distance' keys.
DKPro-sidecar measures (topic_model, structural_stylistic) are routed
externally via dkpro_proxy and have no in-process implementation here.
"""

import math
import time
from functools import partial
from typing import Any

# (measure, backend) pairs whose raw output is already a similarity in [0,1].
_SIMILARITY_KEYS = {
    ("tfidf_cosine", "sklearn"),
    ("embedding_cosine", "gensim"),
    ("sbert_cosine", "sentence_transformers"),
    ("cross_encoder", "sentence_transformers"),
    ("wordnet_similarity", "nltk"),
    ("token_set_overlap", "builtin"),
}


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
    else:
        result["distance"] = raw
        result["similarity"] = 1.0 / (1.0 + raw) if raw >= 0 else 0.0
    return result


# ─── Embedding cosine (gensim) ────────────────────────────────────────────────

# Known static-embedding variants -> gensim-data model name. Any model can be
# selected directly via params.model_name; the variant is a convenience alias
# for the published gensim-data resource (ConceptNet Numberbatch is distributed
# by gensim-data as a KeyedVectors in word2vec format). Verified against
# gensim.downloader.info()['models'] — the published id is
# conceptnet-numberbatch-17-06-300 (there is no -301 in gensim-data).
_EMBEDDING_VARIANTS = {
    "glove": "glove-wiki-gigaword-50",
    "fasttext": "fasttext-wiki-news-subwords-300",
    "conceptnet_numberbatch": "conceptnet-numberbatch-17-06-300",
}


def _embedding_cosine_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_gensim_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "glove")
    model_name = params.get("model_name") or _EMBEDDING_VARIANTS.get(variant, "glove-wiki-gigaword-50")
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


# ─── TF-IDF cosine (scikit-learn) ────────────────────────────────────────────


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


# ─── Token-set overlap (jaccard / dice variants, CPU-only, no model) ─────────

# Canonical family: ``token_set_overlap`` with ``params.variant`` selecting the
# normalisation (analogous to the ``embedding_cosine`` variant pattern). The two
# normalisations are monotone transformations of each other (dice = 2j/(1+j)) and
# produce the same ranking — only the scale differs. ``jaccard`` and ``dice`` are
# legacy aliases that pin the variant via functools.partial (same pattern as
# ``lexical.py``), so existing API consumers keep working unchanged.


def _tokenize(text: str) -> set[str]:
    """Minimal deterministic tokenizer: lowercase + whitespace split."""
    return set(text.lower().split())


def _token_set_overlap(input_data: dict[str, Any], params: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
    """Token-set overlap — params.variant "jaccard" (default) or "dice"; aliases pin it."""
    variant = variant or params.get("variant", "jaccard")
    a = _tokenize(input_data.get("text_a", ""))
    b = _tokenize(input_data.get("text_b", ""))
    if not a and not b:
        raw = 1.0  # both empty -> identical
    elif not a or not b:
        raw = 0.0
    elif variant == "dice":
        raw = 2 * len(a & b) / (len(a) + len(b))
    else:
        raw = len(a & b) / len(a | b)
    return _normalize_similarity(raw, "token_set_overlap", "builtin")


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
    ("embedding_cosine", "gensim"): _embedding_cosine_gensim,
    ("sbert_cosine", "sentence_transformers"): _sbert_cosine,
    ("wmd", "gensim"): _wmd_gensim,
    ("cross_encoder", "sentence_transformers"): _cross_encoder,
    ("wordnet_similarity", "nltk"): _wordnet_similarity_nltk,
    ("tfidf_cosine", "sklearn"): _tfidf_cosine_sklearn,
    ("token_set_overlap", "builtin"): _token_set_overlap,
    ("jaccard", "builtin"): partial(_token_set_overlap, variant="jaccard"),
    ("dice", "builtin"): partial(_token_set_overlap, variant="dice"),
    ("bertscore", "bertscore"): _bertscore,
}

DEFAULT_BACKENDS: dict[str, str] = {
    "embedding_cosine": "gensim",
    "sbert_cosine": "sentence_transformers",
    "wmd": "gensim",
    "cross_encoder": "sentence_transformers",
    "wordnet_similarity": "nltk",
    "tfidf_cosine": "sklearn",
    "token_set_overlap": "builtin",
    "jaccard": "builtin",
    "dice": "builtin",
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
