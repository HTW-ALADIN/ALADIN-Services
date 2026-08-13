"""Retrieval computation implementations for Tier 1 (Spec A).

Each function takes input dict and params dict, returns a result dict
with the ranked list of matches.
"""

import time
from typing import Any


def _fuzzy_extract_rapidfuzz(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from rapidfuzz import process

    query = input_data.get("query", "")
    candidates = input_data.get("candidates", [])
    scorer_name = params.get("scorer", "WRatio")
    limit = params.get("limit", 5)
    score_cutoff = params.get("score_cutoff")

    # Map scorer name to function
    from rapidfuzz import fuzz

    scorer_map = {
        "ratio": fuzz.ratio,
        "partial_ratio": fuzz.partial_ratio,
        "token_sort_ratio": fuzz.token_sort_ratio,
        "token_set_ratio": fuzz.token_set_ratio,
        "WRatio": fuzz.WRatio,
    }
    scorer = scorer_map.get(scorer_name, fuzz.WRatio)

    results = process.extract(query, candidates, scorer=scorer, limit=limit, score_cutoff=score_cutoff)
    ranked = [{"candidate": r[0], "score": float(r[1]), "index": r[2]} for r in results]
    return {"matches": ranked, "count": len(ranked)}


def _semantic_search_sbert(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from sentence_transformers import util

    from .model_cache import get_sbert_model

    query = input_data.get("query", "")
    candidates = input_data.get("candidates", [])
    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    top_k = params.get("top_k", 10)

    model = get_sbert_model(model_name)
    query_emb = model.encode([query], convert_to_tensor=True)
    corpus_emb = model.encode(candidates, convert_to_tensor=True)

    hits = util.semantic_search(query_emb, corpus_emb, top_k=top_k)[0]
    ranked = [{"candidate": candidates[h["corpus_id"]], "score": float(h["score"]), "corpus_id": h["corpus_id"]} for h in hits]
    return {"matches": ranked, "count": len(ranked)}


def _semantic_search_gensim(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    query = input_data.get("query", "")
    candidates = input_data.get("candidates", [])
    top_k = params.get("top_k", 10)

    all_docs = [query] + candidates
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(all_docs)
    query_vec = tfidf[0:1]
    corpus_vec = tfidf[1:]
    sims = cosine_similarity(query_vec, corpus_vec)[0]
    top_indices = np.argsort(sims)[::-1][:top_k]

    ranked = [{"candidate": candidates[int(i)], "score": float(sims[int(i)]), "corpus_id": int(i)} for i in top_indices]
    return {"matches": ranked, "count": len(ranked)}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

RETRIEVAL_DISPATCH: dict[tuple[str, str], Any] = {
    ("fuzzy_extract", "rapidfuzz"): _fuzzy_extract_rapidfuzz,
    ("semantic_search", "sentence_transformers"): _semantic_search_sbert,
    ("semantic_search", "gensim"): _semantic_search_gensim,
}

DEFAULT_RETRIEVAL_BACKENDS: dict[str, str] = {
    "fuzzy_extract": "rapidfuzz",
    "semantic_search": "sentence_transformers",
}


def compute_retrieval(method: str, backend: str | None, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Compute a retrieval operation and return the result dict."""
    if backend is None:
        backend = DEFAULT_RETRIEVAL_BACKENDS.get(method, "rapidfuzz")

    key = (method, backend)
    func = RETRIEVAL_DISPATCH.get(key)
    if func is None:
        raise ValueError(f"Unsupported combination: method={method}, backend={backend}")

    start = time.monotonic()
    result = func(input_data, params)
    elapsed = time.monotonic() - start
    result["compute_time_ms"] = round(elapsed * 1000, 2)
    return result
