"""Retrieval computations: semantic search (SBERT, [model]-only) and BM25 (base).

The former TF-IDF fallback backend of ``semantic_search`` was removed — BM25 is
now the sole non-model (base-tier) lexical retrieval algorithm. ``semantic_search``
is sentence-transformers only and therefore requires the ``[model]`` extra.
"""

import math
import time
from typing import Any


def _semantic_search_sbert(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from sentence_transformers import util

    from .model_cache import get_sbert_model, require_allowed_model

    query = input_data.get("query", "")
    candidates = input_data.get("candidates", [])
    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    top_k = params.get("top_k", 10)

    require_allowed_model("semantic_search", model_name)
    model = get_sbert_model(model_name)
    query_emb = model.encode([query], convert_to_tensor=True)
    corpus_emb = model.encode(candidates, convert_to_tensor=True)

    hits = util.semantic_search(query_emb, corpus_emb, top_k=top_k)[0]
    ranked = [{"candidate": candidates[h["corpus_id"]], "score": float(h["score"]), "corpus_id": h["corpus_id"]} for h in hits]
    return {"matches": ranked, "count": len(ranked)}


# ─── BM25 (pure stdlib, CPU-only, no model) ──────────────────────────────────


def _bm25_scores(query_terms: list[str], corpus: list[list[str]], k1: float, b: float) -> list[float]:
    """Classic BM25 (Robertson/Sparck Jones) scores, one per corpus doc."""
    n_docs = len(corpus)
    doc_len = [len(doc) for doc in corpus]
    avgdl = sum(doc_len) / n_docs if n_docs else 0.0
    doc_freq: dict[str, int] = {}
    for doc in corpus:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    scores = [0.0] * n_docs
    for term in set(query_terms):
        df = doc_freq.get(term, 0)
        if df == 0 or n_docs == 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for i, doc in enumerate(corpus):
            tf = doc.count(term)
            if tf == 0:
                continue
            denom = tf + k1 * (1 - b + b * doc_len[i] / avgdl) if avgdl > 0 else tf + k1
            scores[i] += idf * (tf * (k1 + 1)) / denom
    return scores


def _bm25(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    query = input_data.get("query", "")
    candidates = input_data.get("candidates", [])
    top_k = params.get("top_k", 10)

    corpus = [doc.lower().split() for doc in candidates]
    scores = _bm25_scores(query.lower().split(), corpus, k1=float(params.get("k1", 1.5)), b=float(params.get("b", 0.75)))
    ranked_ids = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    ranked = [{"candidate": candidates[i], "score": float(scores[i]), "corpus_id": i} for i in ranked_ids]
    return {"matches": ranked, "count": len(ranked)}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

RETRIEVAL_DISPATCH: dict[tuple[str, str], Any] = {
    ("semantic_search", "sentence_transformers"): _semantic_search_sbert,
    ("bm25", "builtin"): _bm25,
}

DEFAULT_RETRIEVAL_BACKENDS: dict[str, str] = {
    "semantic_search": "sentence_transformers",
    "bm25": "builtin",
}


def compute_retrieval(method: str, backend: str | None, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Compute a retrieval operation and return the result dict."""
    if backend is None:
        backend = DEFAULT_RETRIEVAL_BACKENDS.get(method, "")

    key = (method, backend)
    func = RETRIEVAL_DISPATCH.get(key)
    if func is None:
        raise ValueError(f"Unsupported combination: method={method}, backend={backend}")

    start = time.monotonic()
    result = func(input_data, params)
    elapsed = time.monotonic() - start
    result["compute_time_ms"] = round(elapsed * 1000, 2)
    return result
