"""Similarity measures — one function per (measure, backend).

Each function takes input dict and params dict, returns a result dict
with 'raw', 'similarity' (normalized to [0,1]), and 'distance' keys.
DKPro-sidecar measures (topic_model, structural_stylistic) are routed
externally via dkpro_proxy and have no in-process implementation here.
"""

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
    """Normalize raw output to {'raw', 'similarity', 'distance'} with similarity in [0,1].

    ``distance`` is always ``1 - similarity`` so the two fields are mutually
    consistent. For measures whose raw value is already a similarity in [0,1]
    the raw value is used as-is (clamped to stay within the documented range);
    otherwise the raw value is a distance and is mapped into [0,1] monotonically.
    """

    def _clamp_similarity(sim: float) -> float:
        if sim < 0.0:
            return 0.0
        if sim > 1.0:
            return 1.0
        return sim

    result: dict[str, Any] = {"raw": raw}
    key = (measure, backend)
    if key in _SIMILARITY_KEYS:
        # wordnet WUP/LCH/path are similarities in [0,1], but the IC-based
        # variants (res/jcn/lin) are unbounded — clamp so 'similarity' never
        # violates the documented [0,1] range. distance stays consistent.
        result["similarity"] = _clamp_similarity(raw)
        result["distance"] = 1.0 - result["similarity"]
    elif measure == "wmd" and backend == "gensim":
        # WMD is a distance in embedding space (can saturate well above 1).
        # Map monotonically into (0,1] with distance as the raw value.
        result["distance"] = raw
        result["similarity"] = 1.0 / (1.0 + raw) if raw >= 0 else 1.0
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

# The Numberbatch model is owned by the ConceptNet sidecar (ADR-0001); any
# reference to it (variant OR explicit model_name) routes through the sidecar.
_CONCEPTNET_MODEL = "conceptnet-numberbatch-17-06-300"


def _embedding_cosine_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Embedding cosine for the ``gensim`` backend.

    ``params.variant`` selects the model. For ``conceptnet_numberbatch`` there
    is an additional ``params.backend`` selector (a parameter *inside* params,
    distinct from the top-level ``backend`` field which stays ``gensim``):

    - ``params.backend: "local"`` (default) — served by the optional
      ``conceptnet-sidecar`` process over HTTP (see ADR-0001). The main service
      no longer loads the ~3-6 GB Numberbatch model in-process; it forwards the
      pair to the sidecar. If the sidecar is absent, the request fails 502/503
      like a missing DKPro sidecar.
    - ``params.backend: "remote"`` — explicit opt-in to call the public
      api.conceptnet.io relatedness API instead (see ``conceptnet_api``).

    ``glove`` / ``fasttext`` are local-only (no public similarity API exists),
    so ``params.backend: "remote"`` on those variants is rejected; they load the
    local gensim model in-process as before.
    """
    variant = params.get("variant", "glove")
    backend = params.get("backend")
    if backend not in (None, "local", "remote"):
        raise ValueError("params.backend must be 'local' or 'remote'")
    if backend == "remote" and variant != "conceptnet_numberbatch":
        raise ValueError(
            f"params.backend='remote' is only available for variant 'conceptnet_numberbatch'; "
            f"variant '{variant}' has no public similarity API and must use backend 'local'"
        )
    if (variant == "conceptnet_numberbatch" and backend != "remote") or (
        backend != "remote" and params.get("model_name", "").split("/", 1)[-1] == _CONCEPTNET_MODEL
    ):
        # local (default), and any explicit Numberbatch model_name (non-remote) —
        # both are served by the ConceptNet sidecar, never loaded in-process.
        from .conceptnet_client import get_relatedness

        a = input_data.get("text_a", "")
        b = input_data.get("text_b", "")
        lang = str(params.get("lang", "en"))
        item = get_relatedness([{"id": "x", "word_a": a, "word_b": b, "lang": lang}])[0]
        return _conceptnet_sidecar_result(item, params)

    if variant == "conceptnet_numberbatch" and backend == "remote":
        # remote must now be requested explicitly (local is the default).
        from .conceptnet_api import compute_relatedness_remote

        return compute_relatedness_remote(input_data, params)

    from .model_cache import get_gensim_model, require_large_download_ok

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name") or _EMBEDDING_VARIANTS.get(variant, "glove-wiki-gigaword-50")
    # Cost gate: fasttext (~2 GB) downloads need an explicit opt-in BEFORE the
    # first download; glove and already-cached models pass through. (ConceptNet
    # and remote never reach this path anymore.)
    require_large_download_ok(model_name, params)
    kv = get_gensim_model(model_name)

    raw = _gensim_word_similarity(kv, a, b)
    return _normalize_similarity(raw, "embedding_cosine", "gensim")


def _conceptnet_sidecar_result(item: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Build the legacy {raw, similarity, distance} envelope from a sidecar item.

    The sidecar returns raw cosine similarity in [-1, 1] (or None + error for
    out-of-vocabulary words) and stays dumb about normalization; we map its raw
    value through the exact same normalizer as before, so existing clients see an
    identical response shape (see ADR-0001).
    """
    if item.get("score") is None:
        return {"raw": None, "similarity": None, "distance": None, "error": item.get("error") or item.get("id") or "no score"}
    return _normalize_similarity(float(item["score"]), "embedding_cosine", "gensim")


def _gensim_word_similarity(kv, a: str, b: str) -> float:
    """Word-level similarity for glove/fasttext; multi-word falls back to n_similarity."""
    words_a = a.split()
    words_b = b.split()
    if len(words_a) == 1 and len(words_b) == 1:
        return float(kv.similarity(words_a[0], words_b[0]))
    return float(kv.n_similarity(words_a, words_b))


# ─── SBERT cosine ─────────────────────────────────────────────────────────────


def _sbert_cosine(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_sbert_model, require_allowed_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    require_allowed_model("sbert_cosine", model_name)
    model = get_sbert_model(model_name)
    emb = model.encode([a, b])
    from sentence_transformers import util

    sim = float(util.cos_sim(emb[0], emb[1])[0][0])
    return _normalize_similarity(sim, "sbert_cosine", "sentence_transformers")


# ─── WMD ──────────────────────────────────────────────────────────────────────


def _wmd_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_gensim_model, require_large_download_ok

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "glove-wiki-gigaword-50")
    # Same cost gate as embedding_cosine: wmd with a >500 MB model_name (e.g.
    # fasttext) must not silently trigger the download either.
    require_large_download_ok(model_name, params)
    kv = get_gensim_model(model_name)
    raw = float(kv.wmdistance(a.split(), b.split()))
    return _normalize_similarity(raw, "wmd", "gensim")


# ─── Cross-encoder ────────────────────────────────────────────────────────────


def _cross_encoder(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import get_cross_encoder_model, require_allowed_model

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    model_name = params.get("model_name", "cross-encoder/stsb-roberta-base")
    require_allowed_model("cross_encoder", model_name)
    model = get_cross_encoder_model(model_name)
    raw = float(model.predict([(a, b)])[0])
    return _normalize_similarity(raw, "cross_encoder", "sentence_transformers")


# ─── WordNet similarity ───────────────────────────────────────────────────────


def _wordnet_similarity_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from .model_cache import ensure_wordnet

    ensure_wordnet()
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
    from .model_cache import require_allowed_model

    # model_type=None means bert_score derives its curated default (roberta-large
    # for lang='en'); an explicit model_type must be on the allow-list.
    require_allowed_model("bertscore", params.get("model_type"))
    import bert_score

    # Default to English so a caller that sets neither lang nor model_type still
    # works: bert_score maps lang='en' to its curated roberta-large default
    # (which is on the allow-list). Without a default, bert_score raises an
    # AssertionError ("Either lang or model_type should be specified") and
    # the request would 500.
    lang = params.get("lang") or "en"
    P, R, F1 = bert_score.score(
        [input_data.get("text_a", "")],
        [input_data.get("text_b", "")],
        model_type=params.get("model_type"),
        lang=lang,
        idf=params.get("idf", False),
        rescale_with_baseline=params.get("rescale_with_baseline", False),
    )
    f1 = float(F1[0])
    # BERTScore keeps its metric-specific fields, but also exposes the common
    # {raw, similarity, distance} shape every other 'distance' result has, so a
    # generic client that only reads result['similarity'] keeps working. F1 is
    # the natural aggregate (harmonic mean of precision & recall) in [0,1].
    return {
        "precision": float(P[0]),
        "recall": float(R[0]),
        "f1": f1,
        "raw": f1,
        "similarity": f1,
        "distance": 1.0 - f1,
    }


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
