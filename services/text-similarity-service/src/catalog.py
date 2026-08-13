"""Measure/algorithm catalog — single source of truth for GET /v1/text/algorithms.

One entry per (operation, algorithm, backend) combination, mirroring the
edit-distance-service catalog shape. The first backend of each algorithm is
marked ``default: true`` (the auto-selected backend when the request omits it).
"""

from typing import Any

_DEFAULT_RESULT_TYPES = {
    "similarity": "scalar_similarity",
    "retrieval": "retrieval",
    "lexical_relations": "lexical_relations",
}


def _backends(*entries: tuple[str, str]) -> list[dict[str, Any]]:
    """Build the API's backend list; the first entry is marked default."""
    return [{"name": name, "description": desc, "default": i == 0} for i, (name, desc) in enumerate(entries)]


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
) -> list[dict[str, Any]]:
    """Expand one algorithm into one catalog entry per backend."""
    rt = result_type or _DEFAULT_RESULT_TYPES[operation]
    return [
        {
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
        }
        for b in backends
    ]


CATALOG: list[dict[str, Any]] = [
    # ── similarity (semantic) ────────────────────────────────────────────────
    *_entry(
        "similarity",
        "embedding_cosine",
        _backends(("gensim", "gensim KeyedVectors.similarity/n_similarity")),
        "Static word/document embedding cosine similarity",
        score_range="[-1,1]",
        granularity="word",
        stateful=True,
    ),
    *_entry(
        "similarity",
        "sbert_cosine",
        _backends(("sentence_transformers", "SBERT model.encode -> util.cos_sim")),
        "Transformer sentence embedding cosine similarity",
        score_range="[-1,1]",
        granularity="sentence",
        stateful=True,
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
    ),
    *_entry(
        "similarity",
        "cross_encoder",
        _backends(("sentence_transformers", "SBERT CrossEncoder.predict")),
        "Cross-encoder pairwise reranking",
        symmetric=False,
        granularity="sentence",
        stateful=True,
    ),
    *_entry(
        "similarity",
        "wordnet_similarity",
        _backends(
            ("nltk", "NLTK synset path/wup/lch/res/jcn/lin similarity"),
            ("dkpro", "DKPro WordNetComparator (Java sidecar)"),
        ),
        "WordNet path/IC similarity — Path/WUP/LCH/Resnik/JCN/Lin",
        score_range="[0,inf)",
        granularity="word",
        stateful=True,
    ),
    *_entry(
        "similarity",
        "tfidf_cosine",
        _backends(
            ("sklearn", "sklearn TfidfVectorizer + cosine_similarity"),
            ("dkpro", "DKPro CosineSimilarity (Java sidecar)"),
        ),
        "TF-IDF vector-space cosine similarity",
        granularity="document",
        stateful=True,
    ),
    *_entry(
        "similarity",
        "bertscore",
        _backends(("bertscore", "bert_score.score")),
        "Contextual-embedding evaluation metric — P/R/F1",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        result_type="bertscore",
    ),
    *_entry(
        "similarity",
        "topic_model",
        _backends(("dkpro", "DKPro LSA/ESA (Java sidecar)")),
        "Topic-model-based similarity — LSA/ESA",
        granularity="document",
        stateful=True,
    ),
    *_entry(
        "similarity",
        "structural_stylistic",
        _backends(("dkpro", "DKPro n-gram containment/TTR/greedy string tiling (Java sidecar)")),
        "Structural/stylistic text similarity — n-gram containment/TTR/greedy string tiling",
        granularity="document",
        stateful=True,
    ),
    # ── retrieval ──────────────────────────────────────────────────────────
    *_entry(
        "retrieval",
        "semantic_search",
        _backends(
            ("sentence_transformers", "SBERT util.semantic_search/paraphrase_mining"),
            ("gensim", "gensim similarities.MatrixSimilarity/WmdSimilarity"),
        ),
        "Semantic search / nearest-neighbor retrieval over embeddings",
        score_range="[-1,1]",
        symmetric=False,
        granularity="sentence",
        stateful=True,
    ),
    # ── lexical_relations ──────────────────────────────────────────────────
    *_entry(
        "lexical_relations",
        "synonym",
        _backends(("nltk", "NLTK WordNet synset.lemma_names")),
        "Synonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
    *_entry(
        "lexical_relations",
        "antonym",
        _backends(("nltk", "NLTK WordNet lemma.antonyms")),
        "Antonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
    *_entry(
        "lexical_relations",
        "hypernym",
        _backends(("nltk", "NLTK WordNet synset.hypernyms/hyponyms")),
        "Hypernym/Hyponym lookup via WordNet (relation field selects direction)",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
]
