"""Similarity measures — one function per (measure, backend).

Each function takes input dict and params dict, returns a result dict
with 'raw', 'similarity' (normalized to [0,1]), and 'distance' keys.

Every measure is implemented natively (in-process), including the
structural/stylistic family (n-gram containment, type-token ratio, greedy
string tiling) and the topic-model family (corpus-free LSI). There is no
external DKPro Java sidecar anymore — it was removed in favour of lean,
stateless Python equivalents.
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
    ("topic_model", "builtin"),
    ("structural_stylistic", "builtin"),
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
      ``      conceptnet-sidecar`` process over HTTP (see ADR-0001). The main service
      no longer loads the ~3-6 GB Numberbatch model in-process; it forwards the
      pair to the sidecar. If the sidecar is absent, the request fails 502/503
      (soft degradation — the rest of the service keeps working).
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


def sbert_cosine_batch(pairs: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute SBERT cosine similarity for a whole batch in ONE ``model.encode`` call.

    ``pairs`` are ``{"id", "text_a", "text_b"}`` dicts. Encoding every text in a
    single vectorized call (instead of one ``encode([a, b])`` per pair) is far
    faster for large batches and matches the batched local-ConceptNet path's
    request-level batching behaviour.
    """
    import time

    import numpy as np

    from .model_cache import get_sbert_model, require_allowed_model

    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    require_allowed_model("sbert_cosine", model_name)
    model = get_sbert_model(model_name)

    # De-duplicate texts so an identical string is encoded once, not per pair.
    texts: list[str] = []
    index: dict[str, int] = {}
    for p in pairs:
        for t in (p["text_a"], p["text_b"]):
            if t not in index:
                index[t] = len(texts)
                texts.append(t)

    start = time.monotonic()
    embeddings = model.encode(texts)
    elapsed = time.monotonic() - start

    results = []
    for p in pairs:
        va = embeddings[index[p["text_a"]]]
        vb = embeddings[index[p["text_b"]]]
        na = float(np.linalg.norm(va))
        nb = float(np.linalg.norm(vb))
        if na == 0.0 or nb == 0.0:
            sim = 0.0
        else:
            sim = float(np.dot(va, vb) / (na * nb))
        res = _normalize_similarity(sim, "sbert_cosine", "sentence_transformers")
        res["compute_time_ms"] = round(elapsed * 1000, 2)
        results.append({"id": p["id"], "result": res})
    return results


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


_IC_VARIANTS = {"res", "jcn", "lin"}


def _wordnet_similarity_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    from .model_cache import ensure_wordnet

    ensure_wordnet()

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "path")

    # IC-based variants (res/jcn/lin) load the Information-Content corpus server-side
    # (cached). ``params.ic`` only selects which published wordnet_ic file to use
    # (e.g. "ic-brown.dat"); a raw IC object cannot cross the JSON boundary because
    # its integer synset-offset keys would be coerced to strings.
    ic = None
    if variant in _IC_VARIANTS:
        from .model_cache import get_wordnet_ic

        ic = get_wordnet_ic(params.get("ic"))

    synsets_a = wn.synsets(a)
    synsets_b = wn.synsets(b)
    if not synsets_a or not synsets_b:
        return {"raw": None, "similarity": None, "distance": None, "error": f"No synsets found for '{a}' or '{b}'"}

    best = -1.0
    for sa in synsets_a:
        for sb in synsets_b:
            try:
                if variant == "wup":
                    val = sa.wup_similarity(sb)
                elif variant == "lch":
                    val = sa.lch_similarity(sb)
                elif variant == "res":
                    val = sa.res_similarity(sb, ic)
                elif variant == "jcn":
                    val = sa.jcn_similarity(sb, ic)
                elif variant == "lin":
                    val = sa.lin_similarity(sb, ic)
                else:  # path
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


# ─── Topic model (corpus-free LSI) ────────────────────────────────────────────
#
# ``topic_model`` replaces the retired DKPro LSA/ESA sidecar with a lean,
# stateless, in-process equivalent. There is no pre-trained external corpus: the
# latent semantic space is derived purely from the two input documents (their
# TF-IDF vectors projected onto the dominant singular components), which yields
# real, meaningful scores for any pair of texts without any model artefact or
# training step. ``variant`` mirrors the DKPro naming: ``lsa`` (default) / ``esa``
# (accepted as aliases — the projection is LSA in both cases).


def _topic_model(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import normalize

    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")

    vectorizer = TfidfVectorizer(
        max_features=params.get("max_features"),
        ngram_range=tuple(params.get("ngram_range", (1, 1))),
    )
    tfidf = vectorizer.fit_transform([a, b])
    # Guard against the degenerate single-document / zero-width case: with
    # nothing to project, fall back to plain TF-IDF cosine similarity.
    if tfidf.shape[0] < 2 or tfidf.nnz == 0 or len(vectorizer.get_feature_names_out()) == 0:
        sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        return _normalize_similarity(sim, "tfidf_cosine", "sklearn")

    # Project into a reduced latent space (LSI) and normalize the projected rows.
    # With < 2 features the SVD degenerates to a single component whose variance
    # ratio divides by zero — fall back to plain TF-IDF cosine in that case.
    if tfidf.shape[1] < 2:
        sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        return _normalize_similarity(sim, "tfidf_cosine", "sklearn")

    k = min(2, tfidf.shape[1])
    # TruncatedSVD emits a benign division-by-zero RuntimeWarning when two very
    # short/disjoint documents yield a zero-variance component; the result it is
    # still usable, but we suppress that single warning and validate the output
    # ourselves (NaN latent/explained-variance -> fall back to TF-IDF cosine).
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        svd = TruncatedSVD(n_components=k, random_state=42)
        latent = svd.fit_transform(tfidf)

    if np.isnan(latent).any() or np.isnan(svd.explained_variance_ratio_).any():
        sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        return _normalize_similarity(sim, "tfidf_cosine", "sklearn")

    latent = normalize(latent, norm="l2", axis=1)
    sim = float(cosine_similarity(latent[0:1], latent[1:2])[0][0])
    return _normalize_similarity(sim, "topic_model", "builtin")


# ─── Structural / stylistic ───────────────────────────────────────────────────
#
# ``structural_stylistic`` replaces the retired DKPro Java sidecar with natively
# implemented, stateless measures: n-gram containment, type-token ratio and
# greedy string tiling (the same families DKPro exposed).
#
# output: similarity is always in [0,1] (higher = more similar). Each underlying
# raw value is a similarity already in [0,1], so raw/similarity are identical.


def _tokenize_words(text: str) -> list[str]:
    """Deterministic lowercase whitespace tokenization (same as the token-set family)."""
    return text.lower().split()


def _tokenize_chars(text: str) -> list[str]:
    """Character-level tokenization for n-gram containment over packed text."""
    return list(text.lower())


def _n_grams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)} if n > 0 and len(tokens) >= n else set()


def _type_token_ratio(text: str) -> float:
    """Type-token ratio: distinct tokens / total tokens (0 if no tokens)."""
    tokens = _tokenize_words(text)
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def _ngram_containment_similarity(a: str, b: str, n: int) -> float:
    """Fraction of a's n-grams contained in b (symmetric containment average)."""
    grams_a, grams_b = _n_grams(_tokenize_words(a), n), _n_grams(_tokenize_words(b), n)
    if not grams_a or not grams_b:
        # Fall back to character n-grams for very short/empty inputs.
        grams_a, grams_b = _n_grams(_tokenize_chars(a), n), _n_grams(_tokenize_chars(b), n)
    if not grams_a and not grams_b:
        return 1.0  # both empty
    if not grams_a or not grams_b:
        return 0.0
    left = len(grams_a & grams_b) / len(grams_a)
    right = len(grams_a & grams_b) / len(grams_b)
    return (left + right) / 2.0


def _greedy_string_tiling_similarity(a: str, b: str, min_match: int) -> float:
    """Greedy string tiling similarity — fraction of matched characters.

    Implements the classic Greedy-String-Tiling algorithm (Zhang/Shasha style)
    over character tokens: repeatedly find the longest common substring between
    the still-unmatched regions and mark those pairs, then score = matched / total.
    """
    if not a or not b:
        return 1.0 if (not a and not b) else 0.0
    chars_a, chars_b = list(a.lower()), list(b.lower())
    n, m = len(chars_a), len(chars_b)
    matched_a = [False] * n
    matched_b = [False] * m
    min_len = max(1, min_match)
    changed = True
    min_ab = min(n, m)

    while changed and min_len <= min_ab:
        changed = False
        max_len = -1
        best: list[tuple[int, int]] = []
        # Find the longest common run of unmatched characters.
        for i in range(n):
            if matched_a[i]:
                continue
            for j in range(m):
                if matched_b[j]:
                    continue
                run = 0
                while (
                    i + run < n
                    and j + run < m
                    and not matched_a[i + run]
                    and not matched_b[j + run]
                    and chars_a[i + run] == chars_b[j + run]
                ):
                    run += 1
                if run > max_len:
                    max_len = run
                    best = [(i, j)]
                elif run == max_len:
                    best.append((i, j))
        if max_len == -1:
            break
        if max_len >= min_len:
            for i, j in best:
                for k in range(max_len):
                    matched_a[i + k] = True
                    matched_b[j + k] = True
            changed = True
        else:
            break

    matched = sum(matched_a)
    total = n + m
    if total == 0:
        return 1.0
    # Normalize by the sum of lengths (classic GST scoring); both-empty handled above.
    return (2 * matched) / total


def _structural_stylistic(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    variant = params.get("variant", "ngram_containment")

    if variant == "type_token_ratio":
        # Mirror DKPro's TTR similarity: 1 - |ttr1 - ttr2|.
        raw = 1.0 - abs(_type_token_ratio(a) - _type_token_ratio(b))
    elif variant == "greedy_string_tiling":
        raw = _greedy_string_tiling_similarity(a, b, int(params.get("min_match", 2)))
    elif variant == "ngram_containment":
        raw = _ngram_containment_similarity(a, b, int(params.get("n", 3)))
    elif variant == "pos_ngram":
        # POS-level n-gram containment is degenerate without a tagger; use the
        # word-class n-gram containment as a lightweight approximation.
        raw = _ngram_containment_similarity(a, b, int(params.get("n", 3)))
    else:
        raise ValueError(f"unsupported structural_stylistic variant '{variant}'")
    result = _normalize_similarity(raw, "structural_stylistic", "builtin")
    return result


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
    ("topic_model", "builtin"): _topic_model,
    ("structural_stylistic", "builtin"): _structural_stylistic,
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
    "topic_model": "builtin",
    "structural_stylistic": "builtin",
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
