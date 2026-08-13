# Unified REST API Specification for the Text-Similarity Microservice

This document defines a unified REST API for embedding the selected text-similarity libraries behind a single interface, using discriminated unions to keep the number of distinct endpoints minimal while preserving full parameter fidelity per algorithm and per backend implementation.

The source ranking (`optimal-library-selection-text-similarity.md`) produced three cumulative tiers rather than two, so this document provides three API specs — one per tier — matching the graph-generation precedent's pattern of "each spec reuses the previous spec's endpoints/tags and adds a delta":

- **Spec A** — Tier 1 core set: NLTK + RapidFuzz + sentence-transformers + gensim (16/23 families, 70%)
- **Spec B** — Tier 1+2: Spec A + scikit-learn + textdistance (20/23 families, 87%)
- **Spec C** — Tier 1+2+3, full coverage: Spec B + BERTScore + DKPro Similarity (23/23 families, 100%)

All three specs share the same 4 endpoints and the same envelope structure — only the discriminated-union catalog of operation/measure/backend combinations differs.

---

## 1. Design principles

**One computation endpoint, not one endpoint per algorithm.** All 23 families are exposed through a single `POST /v1/compute` call whose body is a three-level discriminated union: **operation** (the shape of the computation) → **measure/method/relation** (the canonical family) → **backend** (the implementing library, where more than one exists). This avoids a combinatorial explosion of endpoints while exposing each backend's exact, strongly-typed parameter set.

**Operation is the top-level discriminator** because the families genuinely differ in shape, not just in algorithm — this is the text-similarity analogue of the graph spec's "backend is a first-class field":

- **`similarity`** — two inputs in, one normalized score out (Levenshtein ... BERTScore)
- **`retrieval`** — one query + many candidates in, a ranked list out (RapidFuzz's `process.extract`, SBERT's `semantic_search`)
- **`lexical_relations`** — one word in, a set of related words/synsets out (a graph lookup, not a numeric score — per the comparison document's explicit recommendation to keep this separate from the scoring endpoints)

**Backend is explicit, not hidden** — different backends disagree on score direction and range for the "same" family (RapidFuzz's `fuzz.ratio` is 0–100, textdistance's `normalized_similarity` is 0–1, NLTK's `lch_similarity` is unbounded). Hiding this would silently change results between calls. A backend can be omitted, in which case the service auto-selects a documented default.

**Discovery endpoint** (`GET /v1/measures`) exposes the full catalog and JSON Schemas of the discriminated union at runtime, including each measure's score direction/range, symmetry, granularity, and statefulness — so clients never hardcode the union or the normalization rules.

**Computation is decoupled from result retrieval**, exactly as in the graph spec: `POST /v1/compute` returns a Result resource (potentially async for model-loading operations like SBERT encoding, BERTScore, or cross-encoder reranking); the payload is fetched via `GET /v1/results/{id}`.

**Uniform error/validation semantics.** Every operation variant is a member of one JSON Schema union, so standard 400 validation errors (RFC 9457 `application/problem+json`) apply identically regardless of operation or backend.

---

## 2. Shared endpoint set (identical for Spec A, B, and C)

| # | Method & path | Purpose |
|---|---|---|
| 1 | `GET /v1/measures` | Discovery: list all operation/measure/backend combinations, each with its JSON Schema and metadata (score direction, range, symmetry, granularity, statefulness, sync/async). |
| 2 | `POST /v1/compute` | Run a computation. Body = discriminated union (operation [+ measure/method/relation] [+ backend] + input + params). Returns `202 Accepted` (async, with `Location`) for model-loading/heavy operations (SBERT/BERTScore/cross-encoder), or `201 Created` with the result inline for fast, stateless ones — both return a Result resource envelope. |
| 3 | `GET /v1/results/{resultId}` | Retrieve a previously computed result's metadata and payload (score, ranked list, or lexical-relation set, depending on operation). |
| 4 | `DELETE /v1/results/{resultId}` | Release a stored result resource. |

**Optional, non-essential convenience routes** (not counted against the "minimal endpoint" goal; purely additive sugar; can be omitted):
- `POST /v1/encode` (raw embedding vectors / phonetic codes, for clients that want the intermediate representation rather than a score)
- `GET /v1/measures/{measure}` (schema for one family only)

---

## 3. Shared envelope & discriminated-union pattern

### 3.1 Request envelope (`POST /v1/compute`)

```json
{
  "operation": "similarity",          // discriminator level 1 (computation shape)
  "measure": "levenshtein",           // discriminator level 2 (canonical family)
  "backend": "rapidfuzz",             // discriminator level 3 (implementation) — optional
  "input": {
    "text_a": "kitten",
    "text_b": "sitting"
  },
  "params": {
    "weights": [1, 1, 1]
  },
  "output": {                          // shared across all `similarity` operations
    "score_type": "similarity",        // similarity | distance | raw
    "normalize": true                  // rescale to [0,1]
  }
}
```

### 3.2 JSON Schema discriminated union (OpenAPI 3.1 style)

```yaml
ComputeRequest:
  oneOf:
    - $ref: '#/components/schemas/SimilarityRequest'
    - $ref: '#/components/schemas/RetrievalRequest'
    - $ref: '#/components/schemas/LexicalRelationsRequest'
  discriminator:
    propertyName: operation
    mapping:
      similarity: '#/components/schemas/SimilarityRequest'
      retrieval: '#/components/schemas/RetrievalRequest'
      lexical_relations: '#/components/schemas/LexicalRelationsRequest'

# Second-level union: one member per canonical measure
SimilarityRequest:
  type: object
  required: [operation, measure, input]
  properties:
    operation: { const: similarity }
    measure: { enum: [levenshtein, damerau_levenshtein, jaro_winkler, hamming,
                       lcs, token_set, sequence_alignment, compression_ncd,
                       phonetic, tfidf_cosine, embedding_cosine, sbert_cosine,
                       wmd, cross_encoder, bertscore, wordnet_similarity,
                       topic_model, structural_stylistic] }
    backend: { type: string }
    input: { type: object }
    params: { type: object }
  # third-level union, only for measures with >1 backend, resolved via sibling `backend`:
  allOf:
    - if: { properties: { measure: { const: levenshtein } } }
      then:
        properties:
          backend: { enum: [nltk, rapidfuzz, textdistance] }
          params:
            oneOf:
              - $ref: '#/components/schemas/LevenshteinNltkParams'
              - $ref: '#/components/schemas/LevenshteinRapidFuzzParams'
              - $ref: '#/components/schemas/LevenshteinTextdistanceParams'
            discriminator: { propertyName: backend }
```

### 3.3 Response envelope (Result resource)

```json
{
  "id": "res_7a1e...",
  "status": "completed",              // pending | completed | failed
  "operation": "similarity",
  "measure": "levenshtein",
  "backend": "rapidfuzz",
  "input": { "...": "echoed request input" },
  "result": {
    "raw": 3,
    "similarity": 0.5714,
    "distance": 3
  },
  "metadata": {
    "symmetric": true,
    "computeTimeMs": 2,
    "createdAt": "2026-08-13T10:00:00Z"
  },
  "_links": {
    "self": "/v1/results/res_7a1e..."
  }
}
```

Errors use `application/problem+json` (RFC 9457) with an additional `invalidParams: [{ name, reason }]` array, so a single schema serves every operation and backend.

---

## 4. Spec A — Tier 1 (NLTK + RapidFuzz + sentence-transformers + gensim)

### 4.1 `operation: similarity` — measure catalog

| measure tag | Canonical family | backend options | Underlying function |
|---|---|---|---|
| `levenshtein` | Levenshtein edit distance | `nltk` (default) | `nltk.edit_distance(s1, s2, substitution_cost, transpositions=False)` |
| | | `rapidfuzz` | `distance.Levenshtein.distance(s1, s2, weights)` / `.normalized_similarity(...)` |
| `damerau_levenshtein` | Damerau-Levenshtein distance | `nltk` (default) | `nltk.edit_distance(s1, s2, transpositions=True)` |
| | | `rapidfuzz` | `distance.DamerauLevenshtein.normalized_similarity(s1, s2)` |
| `jaro_winkler` | Jaro / Jaro-Winkler similarity (variant sub-field: `jaro` \| `jaro_winkler`) | `rapidfuzz` (only) | `distance.Jaro.normalized_similarity(...)` / `distance.JaroWinkler.normalized_similarity(...)` |
| `hamming` | Hamming distance | `rapidfuzz` (only) | `distance.Hamming.normalized_similarity(s1, s2)` |
| `lcs` | Longest Common Subsequence (variant: `subsequence`) | `rapidfuzz` (only) | `distance.LCSseq.normalized_similarity(s1, s2)` / `distance.Indel.normalized_similarity(...)` |
| `token_set` | Token-set similarity (variant: `jaccard` \| `masi` \| `binary`) | `nltk` (only) | `nltk.jaccard_distance(label1, label2)` / `nltk.masi_distance(...)` / `nltk.binary_distance(...)` |
| `embedding_cosine` | Static word/document-embedding similarity | `gensim` (only) | `KeyedVectors.similarity(w1, w2)` / `KeyedVectors.n_similarity(ws1, ws2)` |
| `sbert_cosine` | Transformer sentence/document-embedding similarity | `sentence_transformers` (only) | `model.encode(sentences)` → `util.cos_sim(a, b)` |
| `wmd` | Word Mover's Distance | `gensim` (only) | `KeyedVectors.wmdistance(document1, document2)` |
| `cross_encoder` | Cross-encoder pairwise reranking (batch pairwise) | `sentence_transformers` (only) | `CrossEncoder(model_name).predict(sentence_pairs)` |
| `wordnet_similarity` | WordNet path/IC similarity (variant: `path` \| `wup` \| `lch` \| `res` \| `jcn` \| `lin`) | `nltk` (only) | `synset.path_similarity(other)` / `.wup_similarity(...)` / `.lch_similarity(...)` / `.res_similarity(other, ic)` / `.jcn_similarity(other, ic)` / `.lin_similarity(other, ic)` |

### 4.2 `operation: retrieval` — method catalog

| method tag | Canonical family | backend options | Underlying function |
|---|---|---|---|
| `fuzzy_extract` | Fuzzy string matching / best-match extraction | `rapidfuzz` (only) | `process.extract(query, choices, scorer, limit)` / `process.extractOne(...)` |
| `semantic_search` | Semantic search / nearest-neighbor retrieval over embeddings (variant: `search` \| `paraphrase_mining`) | `sentence_transformers` (default) | `util.semantic_search(query_embeddings, corpus_embeddings, top_k)` / `util.paraphrase_mining(model, sentences)` |
| | | `gensim` | `similarities.MatrixSimilarity(corpus, num_features)` / `similarities.WmdSimilarity(corpus, w2v_model, num_best)` |

### 4.3 `operation: lexical_relations` — relation catalog

| relation tag | Canonical family | backend options | Underlying function |
|---|---|---|---|
| `synonym` | Synonym lookup | `nltk` (only) | `wn.synsets(lemma)` → aggregate `synset.lemma_names()` |
| `antonym` | Antonym lookup | `nltk` (only) | `lemma.antonyms()` |
| `hypernym` / `hyponym` | Hypernym/Hyponym lookup (relation selects direction) | `nltk` (only) | `synset.hypernyms()` / `synset.hyponyms()` |

16 tags cover the 16 families of Tier 1 (WordNet's six similarity sub-measures are folded into one `wordnet_similarity` tag via a variant sub-discriminator, matching the "minimal number of distinct endpoints" goal from the graph-generation precedent).

### 4.4 Example: multi-backend discriminated union for `levenshtein`

```json
// backend = nltk
{ "operation": "similarity", "measure": "levenshtein", "backend": "nltk",
  "input": { "text_a": "kitten", "text_b": "sitting" },
  "params": { "substitution_cost": 1, "transpositions": false } }

// backend = rapidfuzz (different parameter surface, same family)
{ "operation": "similarity", "measure": "levenshtein", "backend": "rapidfuzz",
  "input": { "text_a": "kitten", "text_b": "sitting" },
  "params": { "weights": [1, 1, 1], "score_cutoff": null } }
```

Both validate against the same top-level `measure: levenshtein` union member but resolve to distinct `params` schemas via the nested `backend` discriminator — preserving full fidelity to each library's native signature instead of forcing a lossy lowest-common-denominator parameter set.

### 4.5 Deployment note

`sbert_cosine`, `cross_encoder`, and the `sentence_transformers` variant of `semantic_search` require model download and benefit from GPU; the service should treat `POST /v1/compute` for these tags as async by default (`202 Accepted` + `Location`) and cache the loaded `SentenceTransformer`/`CrossEncoder` instances as singletons, per the comparison document's stated design implication. gensim-backed tags similarly cache trained `KeyedVectors`/`Doc2Vec` models.

---

## 5. Spec B — Tier 1+2 (Tier 1 + scikit-learn + textdistance)

Spec B reuses all 4 endpoints and all 16 tags from Spec A unchanged, and adds:

- 4 new measure tags, exclusive to textdistance/scikit-learn (families not covered by Tier 1)
- textdistance as an additional backend on 6 existing similarity tags, where it offers a richer or alternative implementation

### 5.1 New tags

| measure tag | Canonical family | backend | Underlying function |
|---|---|---|---|
| `sequence_alignment` | Sequence alignment (variant: `needleman_wunsch` \| `gotoh` \| `smith_waterman`) | `textdistance` (only) | `textdistance.needleman_wunsch(s1, s2)` / `.gotoh(...)` / `.smith_waterman(...)` |
| `compression_ncd` | Compression-based distance (variant: `arithmetic` \| `rle` \| `bwt_rle` \| `sqrt` \| `entropy`) | `textdistance` (only) | `textdistance.entropy_ncd(s1, s2)` (and sibling NCD variants) |
| `phonetic` | Phonetic encoding-based comparison (variant: `editex` \| `mra`) | `textdistance` (only) | `textdistance.editex(s1, s2)` / match-rating comparison |
| `tfidf_cosine` | TF-IDF vector-space cosine similarity | `sklearn` (only) | `TfidfVectorizer(...).fit_transform(docs)` → `cosine_similarity(X, Y)` |

### 5.2 Backend extension on existing tags

| measure tag | Added backend | Underlying function | Rationale |
|---|---|---|---|
| `levenshtein` | `textdistance` | `textdistance.levenshtein(s1, s2)` / `.normalized_similarity(...)` | Extra backend option with a distinct normalization convention (`normalized_similarity` in [0,1] vs. RapidFuzz's raw int/0–100 scale). |
| `damerau_levenshtein` | `textdistance` | `textdistance.damerau_levenshtein(...)` | Same rationale. |
| `jaro_winkler` | `textdistance` | `textdistance.jaro(...)` / `.jaro_winkler(...)` | Adds a third implementation alongside RapidFuzz. |
| `hamming` | `textdistance` | `textdistance.hamming(...)` | Same rationale. |
| `lcs` | `textdistance` | `textdistance.lcsseq(s1, s2)` / `.ratcliff_obershelp.normalized_similarity(...)` | Adds Ratcliff-Obershelp, not present in RapidFuzz. |
| `token_set` | `textdistance` | `textdistance.jaccard(seq1, seq2)` / `.sorensen_dice(...)` / `.tversky(...)` / `.overlap(...)` / `.cosine(...)` / `.monge_elkan(...)` / `.bag(...)` | Extends the variant enum on this tag from `{jaccard, masi, binary}` (NLTK) to also include `{sorensen_dice, tversky, overlap, cosine, monge_elkan, bag}` (textdistance) — exposed as an extra backend rather than a new tag to avoid duplicating the family, mirroring how the graph spec added `graph_tool` as an extra backend on `configuration_model`. |

### 5.3 Discovery endpoint delta

`GET /v1/measures` for Spec B returns the same 16 entries as Spec A plus the 4 new tags above, and the 6 extended backend enums — the discriminated union schema is a strict superset, so any client written against Spec A remains valid against Spec B (backward-compatible extension).

---

## 6. Spec C — Tier 1+2+3, full coverage (Spec B + BERTScore + DKPro Similarity)

Spec C reuses all 4 endpoints and all 20 tags from Spec B unchanged, and adds:

- 3 new measure tags, exclusive to bertscore/dkpro
- dkpro as an additional backend on 5 existing similarity tags, where its broad catalog offers a generalized/alternative implementation

### 6.1 New tags

| measure tag | Canonical family | backend | Underlying function |
|---|---|---|---|
| `bertscore` | Contextual-embedding evaluation metric (token-aligned P/R/F1) | `bertscore` (only) | `bert_score.score(cands, refs, model_type, lang, idf, rescale_with_baseline)` |
| `topic_model` | Topic-model-based similarity (variant: `lsa` \| `esa`) | `dkpro` (only) | `LatentSemanticAnalysis.getSimilarity(...)` / `VectorIndexSourceRelatednessResource.getSimilarity(...)` |
| `structural_stylistic` | Structural/stylistic text similarity (variant: `ngram_containment` \| `type_token_ratio` \| `greedy_string_tiling`) | `dkpro` (only) | `WordNGramContainmentMeasure(n).getSimilarity(...)` / `GreedyStringTiling.getSimilarity(...)` / type-token-ratio comparator |

`bertscore`'s result shape is a (Precision, Recall, F1) triple rather than a single scalar — this is why `result` in the shared response envelope carries named fields rather than a bare similarity number; clients that only want a single value can read `result.f1`.

### 6.2 Backend extension on existing tags

| measure tag | Added backend | Underlying function | Rationale |
|---|---|---|---|
| `token_set` | `dkpro` | `WordNGramJaccardMeasure(n).getSimilarity(s1, s2)` | Adds DKPro's word-n-gram Jaccard variant alongside NLTK's and textdistance's token measures. |
| `lcs` | `dkpro` | `LongestCommonSubstringComparator.getSimilarity(s1, s2)` | Adds a third LCS implementation. |
| `phonetic` | `dkpro` | (DKPro's phonetic comparator, per its catalog) | DKPro's phonetic catalog entry, exposed as an extra backend rather than a new tag. |
| `tfidf_cosine` | `dkpro` | `CosineSimilarity.getSimilarity(s1, s2)` | Adds an alternative cosine implementation independent of scikit-learn's vectorizer pipeline. |
| `wordnet_similarity` | `dkpro` | `WordNetComparator.getSimilarity(...)` (wraps Resnik/Lin/JCN/Path-style measures) | DKPro's WordNet wrapper offers the same measure family via a different (JVM) implementation. |

### 6.3 Discovery endpoint delta

`GET /v1/measures` for Spec C returns the same 20 entries as Spec B plus the 3 new tags above, and the 5 extended backend enums — again a strict superset, so clients written against Spec B remain valid against Spec C.

### 6.4 Deployment note

Because DKPro Similarity has materially worse packaging ergonomics than the other seven libraries — no PyPI path, Apache UIMA + JVM stack (per `text-similarity-libraries-comparison.md`, §"Per-library details" and §"Design implication") — Spec C's implementation should isolate the `dkpro` backend in its own service/sidecar behind the same `POST /v1/compute` contract (routed internally by the API gateway based on `backend == "dkpro"`), exactly as `graph_tool` was isolated in the graph-generation spec. BERTScore, while pure-Python/PyTorch and PyPI-installable, is flagged inactive upstream (no release in 12+ months) and should be version-pinned and treated as a vendored dependency rather than an actively-supported one; it is also GPU-recommended, so `bertscore` requests should default to the async (`202 Accepted`) path. The public API surface is unaffected either way.

---

## 7. Summary

| | Spec A (Tier 1) | Spec B (Tier 1+2) | Spec C (Tier 1+2+3, full) |
|---|---|---|---|
| **Endpoints** | 4 (`GET /v1/measures`, `POST /v1/compute`, `GET /v1/results/{id}`, `DELETE /v1/results/{id}`) | Same 4 | Same 4 |
| **Backends** | nltk, rapidfuzz, sentence_transformers, gensim | + sklearn, textdistance | + bertscore, dkpro |
| **Operations** | similarity, retrieval, lexical_relations | Same 3 | Same 3 |
| **Similarity/retrieval/relation tags** | 16 | 20 | 23 |
| **Family coverage** | 16/23 (70%) | 20/23 (87%) | 23/23 (100%) |
| **Deployment** | Single container (light NLTK corpus download only) | Single container (adds trivial-dependency sklearn/textdistance) | Primary container + isolated dkpro JVM/UIMA sidecar; bertscore pinned + defaulted to async |