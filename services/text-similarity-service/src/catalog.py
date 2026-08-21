"""Measure/algorithm catalog — single source of truth for GET /v1/similarity/text/algorithms.

One entry per (operation, algorithm, backend) combination, mirroring the
edit-distance-service catalog shape. The first backend of each algorithm is
marked ``default: true`` (the auto-selected backend when the request omits it).

Every entry carries semantic metadata so clients can tell *what kind* of
measure they get without knowing the backing library:

- ``category``: lexical | statistical | word_embedding | sentence_embedding |
  knowledge_graph | retrieval | evaluation | topic | structural
- ``requires_model``: needs the ``[model]`` extra (PyTorch / large downloads) —
  base backends (incl. gensim) omit it
- ``requires_gpu``: always false — the whole service is CPU-capable
- ``language``: language the backend serves (e.g. ``de`` for Odenet)
- ``extra``: pip extra needed to enable the backend (``model``, ``de``,
  ``dkpro``) — base backends omit it
- ``variants``: selectable via ``params.variant`` / ``params.model_name``

Build/run profiles — the same repo builds two images that differ only in the
PyTorch-based (``requires_model``) algorithms:

- ``cpu`` (default) — the base catalog, PyTorch algorithms excluded. This is the
  default (``text-similarity-cpu`` image): it stays small. A request for a
  model algorithm is rejected up-front with 400 pointing at the ``pytorch``
  image rather than a lazy 501.
- ``pytorch`` — full catalog, every algorithm. The ``[model]`` algorithms are
  present and return 501 when the extra isn't installed.

Set via ``SIMILARITY_PROFILE`` (default ``cpu``). The catalog below is the
full, single source of truth; ``get_catalog()`` applies the profile filter.
"""

import os
from typing import Any

PROFILES = ("pytorch", "cpu")
PROFILE = os.environ.get("SIMILARITY_PROFILE", "cpu")
if PROFILE not in PROFILES:
    PROFILE = "cpu"


def is_enabled(entry: dict[str, Any]) -> bool:
    """Whether a catalog entry is available in the active profile."""
    if PROFILE == "pytorch":
        return True
    return not entry.get("requires_model")


_DEFAULT_RESULT_TYPES = {
    "similarity": "scalar_similarity",
    "retrieval": "retrieval",
    "lexical_relations": "lexical_relations",
}


def _backends(*entries: tuple[str, str] | tuple[str, str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the API's backend list; the first entry is marked default.

    Each entry is ``(name, description)`` or ``(name, description, extra_meta)``
    where extra_meta carries backend-specific fields (language, extra, ...).
    """
    result: list[dict[str, Any]] = []
    for i, entry in enumerate(entries):
        name, desc, *meta = entry
        d: dict[str, Any] = {"name": name, "description": desc, "default": i == 0}
        if meta:
            d.update(meta[0])
        result.append(d)
    return result


def _entry(
    operation: str,
    algorithm: str,
    backends: list[dict[str, Any]],
    families: str,
    *,
    score_direction: str = "higher_is_similar",
    score_range: str = "[0,1]",
    symmetric: bool = True,
    granularity: str = "char",
    stateful: bool = False,
    result_type: str | None = None,
    category: str = "",
    requires_model: bool = False,
    requires_gpu: bool = False,
    requires_sidecar: bool = False,
    sidecar: str | None = None,
    is_placeholder: bool = False,
    variants: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Expand one algorithm into one catalog entry per backend."""
    rt = result_type or _DEFAULT_RESULT_TYPES[operation]
    entries: list[dict[str, Any]] = []
    for b in backends:
        entry: dict[str, Any] = {
            "operation": operation,
            "algorithm": algorithm,
            "backend": b["name"],
            "default": b["default"],
            "families": [families],
            "result_type": rt,
            "description": b["description"],
            "score_direction": score_direction,
            "score_range": score_range,
            "symmetric": symmetric,
            "granularity": granularity,
            "stateful": stateful,
            "category": category,
            "requires_model": b.get("requires_model", requires_model),
            "requires_gpu": b.get("requires_gpu", requires_gpu),
            "requires_sidecar": b.get("requires_sidecar", requires_sidecar),
            "sidecar": b.get("sidecar", sidecar),
            "is_placeholder": b.get("is_placeholder", is_placeholder),
        }
        for key in ("language", "extra", "variants", "alias_of", "fixed_variant"):
            if key in b:
                entry[key] = b[key]
        if variants is not None:
            entry["variants"] = entry.get("variants", variants)
        entries.append(entry)
    return entries


CATALOG: list[dict[str, Any]] = [
    # ── similarity (semantic) ────────────────────────────────────────────────
    *_entry(
        "similarity",
        "embedding_cosine",
        _backends(("gensim", "gensim KeyedVectors.similarity/n_similarity")),
        "Static word/document embedding cosine similarity",
        score_range="[0,1]",
        granularity="word",
        stateful=True,
        category="word_embedding",
        # gensim is base-tier (no [model] extra needed). Large runtime downloads
        # (fasttext ~2 GB) are gated by an explicit opt-in, not by a pip extra.
        # ``conceptnet_numberbatch`` (local default) is served by the optional
        # ConceptNet sidecar and is independent of the build profile.
        requires_sidecar=True,
        sidecar="conceptnet",
        variants=["glove", "fasttext", "conceptnet_numberbatch"],
    ),
    *_entry(
        "similarity",
        "sbert_cosine",
        _backends(("sentence_transformers", "SBERT model.encode -> util.cos_sim", {"extra": "model"})),
        "Transformer sentence embedding cosine similarity",
        score_range="[0,1]",
        granularity="sentence",
        stateful=True,
        category="sentence_embedding",
        requires_model=True,
    ),
    *_entry(
        "similarity",
        "wmd",
        _backends(("gensim", "gensim KeyedVectors.wmdistance")),
        "Word Mover's Distance",
        score_direction="lower_is_similar",
        score_range="[0,inf)",
        granularity="document",
        stateful=True,
        category="word_embedding",
    ),
    *_entry(
        "similarity",
        "cross_encoder",
        _backends(("sentence_transformers", "SBERT CrossEncoder.predict", {"extra": "model"})),
        "Cross-encoder pairwise reranking",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        category="sentence_embedding",
        requires_model=True,
    ),
    *_entry(
        "similarity",
        "wordnet_similarity",
        _backends(
            ("nltk", "NLTK synset path/wup/lch/res/jcn/lin similarity"),
            (
                "dkpro",
                "DKPro WordNetComparator (Java sidecar) — placeholder, always returns 0.5",
                {"requires_sidecar": True, "sidecar": "dkpro", "is_placeholder": True},
            ),
        ),
        "WordNet path/IC similarity — Path/WUP/LCH/Resnik/JCN/Lin",
        score_range="[0,inf)",
        granularity="word",
        stateful=True,
        category="lexical",
    ),
    *_entry(
        "similarity",
        "tfidf_cosine",
        _backends(
            ("sklearn", "sklearn TfidfVectorizer + cosine_similarity"),
            (
                "dkpro",
                "DKPro CosineSimilarity (Java sidecar) — placeholder, always returns 0.5",
                {"requires_sidecar": True, "sidecar": "dkpro", "is_placeholder": True},
            ),
        ),
        "TF-IDF vector-space cosine similarity",
        granularity="document",
        stateful=True,
        category="statistical",
    ),
    *_entry(
        "similarity",
        "token_set_overlap",
        _backends(("builtin", "Pure-Python token-set overlap — Jaccard or Dice coefficient (params.variant)")),
        "Token-set overlap — Jaccard / Dice coefficient",
        granularity="token",
        category="statistical",
        variants=["jaccard", "dice"],
    ),
    # Legacy aliases of token_set_overlap (fixed variant) so existing consumers
    # of the old "jaccard" / "dice" algorithm names keep working.
    *_entry(
        "similarity",
        "jaccard",
        _backends(("builtin", "Jaccard (legacy alias)", {"alias_of": "token_set_overlap", "fixed_variant": "jaccard"})),
        "Token-set Jaccard (legacy alias)",
        granularity="token",
        category="statistical",
    ),
    *_entry(
        "similarity",
        "dice",
        _backends(("builtin", "Dice coefficient (legacy alias)", {"alias_of": "token_set_overlap", "fixed_variant": "dice"})),
        "Token-set Dice coefficient (legacy alias)",
        granularity="token",
        category="statistical",
    ),
    *_entry(
        "similarity",
        "bertscore",
        _backends(("bertscore", "bert_score.score", {"extra": "model"})),
        "Contextual-embedding evaluation metric — P/R/F1",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        result_type="bertscore",
        category="evaluation",
        requires_model=True,
    ),
    *_entry(
        "similarity",
        "topic_model",
        _backends(
            (
                "dkpro",
                "DKPro LSA/ESA (Java sidecar) — placeholder, always returns 0.5",
                {"requires_sidecar": True, "sidecar": "dkpro", "is_placeholder": True},
            ),
        ),
        "Topic-model-based similarity — LSA/ESA",
        granularity="document",
        stateful=True,
        category="topic",
        requires_sidecar=True,
        sidecar="dkpro",
        is_placeholder=True,
    ),
    *_entry(
        "similarity",
        "structural_stylistic",
        _backends(
            (
                "dkpro",
                "DKPro n-gram containment/TTR/greedy string tiling (Java sidecar) — placeholder, always returns 0.5",
                {"requires_sidecar": True, "sidecar": "dkpro", "is_placeholder": True},
            ),
        ),
        "Structural/stylistic text similarity — n-gram containment/TTR/greedy string tiling",
        granularity="document",
        stateful=True,
        category="structural",
        requires_sidecar=True,
        sidecar="dkpro",
        is_placeholder=True,
    ),
    # ── retrieval ──────────────────────────────────────────────────────────
    # semantic_search is sentence-transformers only ([model]-only) — the former
    # TF-IDF (gensim) fallback backend was removed; BM25 is the sole base-tier
    # non-model retrieval algorithm.
    *_entry(
        "retrieval",
        "semantic_search",
        _backends(
            ("sentence_transformers", "SBERT util.semantic_search/paraphrase_mining", {"requires_model": True, "extra": "model"}),
        ),
        "Semantic search / nearest-neighbor retrieval over embeddings",
        score_range="[-1,1]",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        category="retrieval",
        requires_model=True,
    ),
    *_entry(
        "retrieval",
        "bm25",
        _backends(("builtin", "Classic BM25 (Robertson/Sparck Jones), pure stdlib")),
        "BM25 lexical retrieval",
        symmetric=False,
        granularity="token",
        stateful=True,
        category="retrieval",
    ),
    # ── lexical_relations ──────────────────────────────────────────────────
    *_entry(
        "lexical_relations",
        "synonym",
        _backends(
            ("nltk", "NLTK WordNet synset.lemma_names"),
            ("odenet", "Open German WordNet synonym (German, via wn)", {"language": "de", "extra": "de"}),
        ),
        "Synonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
        category="lexical",
    ),
    *_entry(
        "lexical_relations",
        "antonym",
        _backends(
            ("nltk", "NLTK WordNet lemma.antonyms"),
            ("odenet", "Open German WordNet antonym (German, via wn)", {"language": "de", "extra": "de"}),
        ),
        "Antonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
        category="lexical",
    ),
    *_entry(
        "lexical_relations",
        "hypernym",
        _backends(
            ("nltk", "NLTK WordNet synset.hypernyms/hyponyms"),
            ("odenet", "Open German WordNet hypernym (German, via wn)", {"language": "de", "extra": "de"}),
        ),
        "Hypernym/Hyponym lookup via WordNet (relation field selects direction)",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
        category="lexical",
    ),
    *_entry(
        "lexical_relations",
        "hyponym",
        _backends(
            ("nltk", "NLTK WordNet synset.hyponyms"),
            ("odenet", "Open German WordNet hyponym (German, via wn)", {"language": "de", "extra": "de"}),
        ),
        "Hyponym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
        category="lexical",
    ),
]


def get_catalog() -> list[dict[str, Any]]:
    """The catalog for the active profile (see ``catalog`` / ``is_enabled``)."""
    if PROFILE == "pytorch":
        return CATALOG
    return [e for e in CATALOG if is_enabled(e)]
