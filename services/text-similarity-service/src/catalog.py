"""Measure/algorithm catalog for the text similarity service.

Defines the full discriminated union of operation/measure/backend combinations
with metadata (score direction, range, symmetry, granularity, statefulness,
sync/async). This is the single source of truth for GET /v1/measures.

Organized by Spec level:
- Spec A (Tier 1): 16 tags — NLTK + RapidFuzz + sentence-transformers + gensim
- Spec B (Tier 1+2): +4 tags — scikit-learn + textdistance
- Spec C (Tier 1+2+3): +3 tags — BERTScore + DKPro Similarity
"""

from typing import Any


def _measure_entry(
    operation: str,
    tag: str,
    backends: list[dict[str, Any]],
    description: str = "",
    score_direction: str = "higher_is_similar",
    score_range: str = "[0,1]",
    symmetric: bool = True,
    granularity: str = "char",
    stateful: bool = False,
    async_default: bool = False,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "tag": tag,
        "backends": backends,
        "description": description,
        "score_direction": score_direction,
        "score_range": score_range,
        "symmetric": symmetric,
        "granularity": granularity,
        "stateful": stateful,
        "async_default": async_default,
    }


def _backend(name: str, description: str = "", default: bool = False) -> dict[str, Any]:
    return {"name": name, "description": description, "default": default}


# ─── Spec A — Tier 1 (NLTK + RapidFuzz + sentence-transformers + gensim) ─────

SPEC_A_CATALOG: list[dict[str, Any]] = [
    # ── similarity ──────────────────────────────────────────────────────────
    _measure_entry(
        "similarity",
        "levenshtein",
        backends=[_backend("nltk", "nltk.edit_distance", default=True), _backend("rapidfuzz", "rapidfuzz.distance.Levenshtein")],
        description="Levenshtein edit distance",
        score_direction="lower_is_similar",
        score_range="[0,inf)",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "damerau_levenshtein",
        backends=[
            _backend("nltk", "nltk.edit_distance(transpositions=True)", default=True),
            _backend("rapidfuzz", "rapidfuzz.distance.DamerauLevenshtein"),
        ],
        description="Damerau-Levenshtein distance",
        score_direction="lower_is_similar",
        score_range="[0,inf)",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "jaro_winkler",
        backends=[_backend("rapidfuzz", "rapidfuzz.distance.Jaro/JaroWinkler", default=True)],
        description="Jaro / Jaro-Winkler similarity",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "hamming",
        backends=[_backend("rapidfuzz", "rapidfuzz.distance.Hamming", default=True)],
        description="Hamming distance",
        score_direction="lower_is_similar",
        score_range="[0,inf)",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "lcs",
        backends=[_backend("rapidfuzz", "rapidfuzz.distance.LCSseq/Indel", default=True)],
        description="Longest Common Subsequence",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "token_set",
        backends=[_backend("nltk", "nltk.jaccard_distance/masi_distance/binary_distance", default=True)],
        description="Token-set similarity — Jaccard/MASI/Binary distance",
        score_direction="lower_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="token",
    ),
    _measure_entry(
        "similarity",
        "embedding_cosine",
        backends=[_backend("gensim", "gensim KeyedVectors.similarity/n_similarity", default=True)],
        description="Static word/document embedding cosine similarity",
        score_direction="higher_is_similar",
        score_range="[-1,1]",
        symmetric=True,
        granularity="word",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "sbert_cosine",
        backends=[_backend("sentence_transformers", "SBERT model.encode -> util.cos_sim", default=True)],
        description="Transformer sentence embedding cosine similarity",
        score_direction="higher_is_similar",
        score_range="[-1,1]",
        symmetric=True,
        granularity="sentence",
        stateful=True,
        async_default=True,
    ),
    _measure_entry(
        "similarity",
        "wmd",
        backends=[_backend("gensim", "gensim KeyedVectors.wmdistance", default=True)],
        description="Word Mover's Distance",
        score_direction="lower_is_similar",
        score_range="[0,inf)",
        symmetric=True,
        granularity="document",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "cross_encoder",
        backends=[_backend("sentence_transformers", "SBERT CrossEncoder.predict", default=True)],
        description="Cross-encoder pairwise reranking",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        async_default=True,
    ),
    _measure_entry(
        "similarity",
        "wordnet_similarity",
        backends=[_backend("nltk", "NLTK synset path/wup/lch/res/jcn/lin similarity", default=True)],
        description="WordNet path/IC similarity — Path/WUP/LCH/Resnik/JCN/Lin",
        score_direction="higher_is_similar",
        score_range="[0,inf)",
        symmetric=True,
        granularity="word",
        stateful=True,
    ),
    # ── retrieval ───────────────────────────────────────────────────────────
    _measure_entry(
        "retrieval",
        "fuzzy_extract",
        backends=[_backend("rapidfuzz", "RapidFuzz process.extract/extractOne", default=True)],
        description="Fuzzy string matching / best-match extraction",
        score_direction="higher_is_similar",
        score_range="[0,100]",
        symmetric=False,
        granularity="char",
    ),
    _measure_entry(
        "retrieval",
        "semantic_search",
        backends=[
            _backend("sentence_transformers", "SBERT util.semantic_search/paraphrase_mining", default=True),
            _backend("gensim", "gensim similarities.MatrixSimilarity/WmdSimilarity"),
        ],
        description="Semantic search / nearest-neighbor retrieval over embeddings",
        score_direction="higher_is_similar",
        score_range="[-1,1]",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        async_default=True,
    ),
    # ── lexical_relations ───────────────────────────────────────────────────
    _measure_entry(
        "lexical_relations",
        "synonym",
        backends=[_backend("nltk", "NLTK WordNet synset.lemma_names", default=True)],
        description="Synonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
    _measure_entry(
        "lexical_relations",
        "antonym",
        backends=[_backend("nltk", "NLTK WordNet lemma.antonyms", default=True)],
        description="Antonym lookup via WordNet",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
    _measure_entry(
        "lexical_relations",
        "hypernym",
        backends=[_backend("nltk", "NLTK WordNet synset.hypernyms/hyponyms", default=True)],
        description="Hypernym/Hyponym lookup via WordNet (relation field selects direction)",
        score_direction="",
        score_range="",
        symmetric=False,
        granularity="word",
    ),
]


# ─── Spec B — Tier 1+2 (+ scikit-learn + textdistance) ──────────────────────

SPEC_B_CATALOG: list[dict[str, Any]] = [
    # New tags
    _measure_entry(
        "similarity",
        "sequence_alignment",
        backends=[_backend("textdistance", "textdistance.needleman_wunsch/gotoh/smith_waterman", default=True)],
        description="Sequence alignment — Needleman-Wunsch/Gotoh/Smith-Waterman",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "compression_ncd",
        backends=[_backend("textdistance", "textdistance entropy_ncd and NCD variants", default=True)],
        description="Compression-based Normalized Compression Distance",
        score_direction="lower_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "phonetic",
        backends=[_backend("textdistance", "textdistance.editex / MRA", default=True)],
        description="Phonetic encoding comparison — Editex/MRA",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
    ),
    _measure_entry(
        "similarity",
        "tfidf_cosine",
        backends=[_backend("sklearn", "sklearn TfidfVectorizer + cosine_similarity", default=True)],
        description="TF-IDF vector-space cosine similarity",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="document",
        stateful=True,
    ),
    # Backend extensions on existing Tier-1 tags (Spec B §5.2)
    _measure_entry(
        "similarity",
        "levenshtein",
        backends=[_backend("textdistance", "textdistance.levenshtein")],
        description="Levenshtein edit distance — extra backend",
    ),
    _measure_entry(
        "similarity",
        "damerau_levenshtein",
        backends=[_backend("textdistance", "textdistance.damerau_levenshtein")],
        description="Damerau-Levenshtein distance — extra backend",
    ),
    _measure_entry(
        "similarity",
        "jaro_winkler",
        backends=[_backend("textdistance", "textdistance.jaro/jaro_winkler")],
        description="Jaro / Jaro-Winkler similarity — extra backend",
    ),
    _measure_entry(
        "similarity", "hamming", backends=[_backend("textdistance", "textdistance.hamming")], description="Hamming distance — extra backend"
    ),
    _measure_entry(
        "similarity",
        "lcs",
        backends=[_backend("textdistance", "textdistance.lcsseq/ratcliff_obershelp")],
        description="Longest Common Subsequence / Ratcliff-Obershelp — extra backend",
    ),
    _measure_entry(
        "similarity",
        "token_set",
        backends=[_backend("textdistance", "textdistance.jaccard/sorensen_dice/tversky/overlap/cosine/monge_elkan/bag")],
        description="Token-set similarity — extra textdistance backend",
    ),
]


# ─── Spec C — Tier 1+2+3 (+ BERTScore + DKPro Similarity) ───────────────────

SPEC_C_CATALOG: list[dict[str, Any]] = [
    # New tags
    _measure_entry(
        "similarity",
        "bertscore",
        backends=[_backend("bertscore", "bert_score.score", default=True)],
        description="Contextual-embedding evaluation metric — P/R/F1",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=False,
        granularity="sentence",
        stateful=True,
        async_default=True,
    ),
    _measure_entry(
        "similarity",
        "topic_model",
        backends=[_backend("dkpro", "DKPro LSA/ESA (Java sidecar)", default=True)],
        description="Topic-model-based similarity — LSA/ESA",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="document",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "structural_stylistic",
        backends=[_backend("dkpro", "DKPro n-gram containment/TTR/greedy string tiling (Java sidecar)", default=True)],
        description="Structural/stylistic text similarity — n-gram containment/TTR/greedy string tiling",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="document",
        stateful=True,
    ),
    # Optional backend extensions on existing tags (Spec C §6.2)
    _measure_entry(
        "similarity",
        "token_set",
        backends=[_backend("dkpro", "DKPro WordNGramJaccardMeasure (Java sidecar)")],
        description="Token-set similarity — DKPro backend",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="token",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "lcs",
        backends=[_backend("dkpro", "DKPro LongestCommonSubstringComparator (Java sidecar)")],
        description="Longest Common Substring — DKPro backend",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "phonetic",
        backends=[_backend("dkpro", "DKPro phonetic comparator (Java sidecar)")],
        description="Phonetic comparison — DKPro backend",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="char",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "tfidf_cosine",
        backends=[_backend("dkpro", "DKPro CosineSimilarity (Java sidecar)")],
        description="TF-IDF cosine similarity — DKPro backend",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="document",
        stateful=True,
    ),
    _measure_entry(
        "similarity",
        "wordnet_similarity",
        backends=[_backend("dkpro", "DKPro WordNetComparator (Java sidecar)")],
        description="WordNet similarity — DKPro backend",
        score_direction="higher_is_similar",
        score_range="[0,1]",
        symmetric=True,
        granularity="word",
        stateful=True,
    ),
]


# ─── Combined catalog ─────────────────────────────────────────────────────────


def _merge_catalog_entry(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge a new entry into an existing one, combining backends lists."""
    merged = dict(existing)
    # Merge backends
    existing_backends = {b["name"] for b in existing.get("backends", [])}
    for b in new.get("backends", []):
        if b["name"] not in existing_backends:
            merged["backends"] = list(merged["backends"]) + [b]
            existing_backends.add(b["name"])
    return merged


def get_catalog(spec: str = "C") -> list[dict[str, Any]]:
    """Return the full catalog for the given spec level, merging backends per tag.

    Tags with multiple backends across spec levels are merged into a single entry
    with all backends listed (e.g., levenshtein shows nltk, rapidfuzz, textdistance).
    """
    # Build a map: (operation, tag) -> entry
    entry_map: dict[tuple[str, str], dict[str, Any]] = {}

    for entry in SPEC_A_CATALOG:
        op = entry["operation"]
        tag = entry["tag"]
        entry_map[(op, tag)] = dict(entry)

    if spec in ("B", "C"):
        for entry in SPEC_B_CATALOG:
            op = entry["operation"]
            tag = entry["tag"]
            key = (op, tag)
            if key in entry_map:
                entry_map[key] = _merge_catalog_entry(entry_map[key], entry)
            else:
                entry_map[key] = dict(entry)

    if spec == "C":
        for entry in SPEC_C_CATALOG:
            op = entry["operation"]
            tag = entry["tag"]
            key = (op, tag)
            if key in entry_map:
                entry_map[key] = _merge_catalog_entry(entry_map[key], entry)
            else:
                entry_map[key] = dict(entry)

    return list(entry_map.values())
