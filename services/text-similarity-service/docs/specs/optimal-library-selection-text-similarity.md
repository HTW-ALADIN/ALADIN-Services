# Optimal Library Selection for a Unified Text-Similarity Microservice

This document uses the data from `text-similarity-libraries-comparison.md` to solve a
weighted maximum-coverage / set-cover problem: select the smallest set of libraries
that covers the largest number of distinct text-similarity algorithm families, while
minimizing redundant overlap between the selected libraries, and while favoring
libraries that are actively maintained and expose an API style that is easy to unify
behind a single (Python-first) microservice interface.

## 1. Problem formalization

Let:

- `A = {a_1, ..., a_23}` — the universe of distinct algorithm families (canonical
  similarity/lexical-relation categories, not individual function signatures; e.g.
  "Jaro-Winkler similarity" is one category even though 5 libraries implement it with
  different signatures).
- `L = {NLTK, spaCy, gensim, sentence-transformers, scikit-learn, textdistance,
  RapidFuzz, jellyfish, BERTScore, WS4J, DKPro Similarity, py_stringmatching}` —
  candidate libraries. **PolyFuzz** and **python-Levenshtein** are excluded *a priori*:
  PolyFuzz only orchestrates calls into TF-IDF/RapidFuzz/embedding backends and
  implements no algorithm of its own (exactly analogous to `rigraph` wrapping the same
  C core as `python-igraph` in the graph-generation analysis); python-Levenshtein is now
  a thin wrapper maintained by the RapidFuzz org over RapidFuzz's own C core and adds
  zero net-new coverage.
- `cover(l) ⊆ A` — the set of algorithm families implemented by library `l`.
- `Q(l) = freshness(l) × api_compat(l)` — a quality weight in `[0, 1]` per library.

We want to choose `S ⊆ L` minimizing `|S|`, such that `⋃_{l∈S} cover(l)` is as close to
`A` as possible, while maximizing:

```
score(S) = Σ_{l∈S} Q(l) × |new(l, S)|
```

where `new(l, S)` is the set of algorithm families `l` adds that were not already
covered by libraries already chosen in `S` (this is what enforces "minimal overlap" —
each added library must justify its inclusion mainly through new coverage, not
duplicate coverage).

This is the classic weighted maximum coverage problem (NP-hard in general); we solve
it with the standard greedy approximation (pick, at each step, the library maximizing
`Q(l) × |new(l, S)|`), which is within a `(1 − 1/e)` factor of optimal.

---

## 2. Algorithm family universe

| # | Algorithm family |
|---|---|
| 1 | Levenshtein edit distance |
| 2 | Damerau-Levenshtein distance |
| 3 | Jaro / Jaro-Winkler similarity |
| 4 | Hamming distance |
| 5 | Longest Common Subsequence/Substring (incl. Ratcliff-Obershelp) |
| 6 | Token-set similarity (Jaccard / Dice / Tversky / Overlap / Cosine over token bags) |
| 7 | Sequence alignment (Needleman-Wunsch / Smith-Waterman / Gotoh) |
| 8 | Compression-based distance (Normalized Compression Distance family) |
| 9 | Phonetic encoding (Soundex / Metaphone / NYSIIS / Match Rating / Editex) |
| 10 | Fuzzy string matching / best-match extraction (ratio-style + batch `process.extract`) |
| 11 | TF-IDF vector-space cosine similarity (classic VSM, document-level) |
| 12 | Static word/document-embedding similarity (Word2Vec / FastText / spaCy vectors) |
| 13 | Transformer sentence/document-embedding similarity (SBERT-style) |
| 14 | Word Mover's Distance |
| 15 | Contextual-embedding evaluation metric (BERTScore-style token-aligned P/R/F1) |
| 16 | Cross-encoder pairwise reranking |
| 17 | Semantic search / nearest-neighbor retrieval over embeddings |
| 18 | WordNet path/information-content semantic similarity (Path, WUP, LCH, Resnik, JCN, Lin) |
| 19 | Synonym lookup |
| 20 | Antonym lookup |
| 21 | Hypernym/Hyponym lookup |
| 22 | Topic-model-based similarity (LSA / ESA) |
| 23 | Structural/stylistic text similarity (n-gram containment, type-token ratio, greedy string tiling) |

---

## 3. Coverage matrix

✓ = implemented, – = not implemented (per the signatures documented in the source comparison).

| # | Family | NLTK | spaCy | gensim | SBERT | sklearn | textdist. | RapidFuzz | jellyfish | BERTScore | WS4J | DKPro | py_strmatch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Levenshtein | ✓ | – | – | – | – | ✓ | ✓ | ✓ | – | – | – | ✓ |
| 2 | Damerau-Levenshtein | ✓ | – | – | – | – | ✓ | ✓ | ✓ | – | – | – | – |
| 3 | Jaro / Jaro-Winkler | – | – | – | – | – | ✓ | ✓ | ✓ | – | – | ✓ | ✓ |
| 4 | Hamming | – | – | – | – | – | ✓ | ✓ | ✓ | – | – | – | – |
| 5 | LCS / LCSubstring | – | – | – | – | – | ✓ | ✓ | – | – | – | ✓ | – |
| 6 | Token-set (Jaccard/Dice/…) | ✓ | – | – | – | – | ✓ | – | – | – | – | ✓ | ✓ |
| 7 | Sequence alignment (NW/SW) | – | – | – | – | – | ✓ | – | – | – | – | – | ✓ |
| 8 | Compression-based (NCD) | – | – | – | – | – | ✓ | – | – | – | – | – | – |
| 9 | Phonetic encoding | – | – | – | – | – | ✓ | – | ✓ | – | – | ✓ | ✓ |
| 10 | Fuzzy matching / extract | – | – | – | – | – | – | ✓ | – | – | – | – | – |
| 11 | TF-IDF vector-space cosine | – | – | – | – | ✓ | – | – | – | – | – | ✓ | ✓ |
| 12 | Static word/doc embedding | – | ✓ | ✓ | – | – | – | – | – | – | – | – | – |
| 13 | Transformer sentence embedding | – | – | – | ✓ | – | – | – | – | – | – | – | – |
| 14 | Word Mover's Distance | – | – | ✓ | – | – | – | – | – | – | – | – | – |
| 15 | Contextual eval. metric | – | – | – | – | – | – | – | – | ✓ | – | – | – |
| 16 | Cross-encoder reranking | – | – | – | ✓ | – | – | – | – | – | – | – | – |
| 17 | Semantic search / NN retrieval | – | – | ✓ | ✓ | – | – | – | – | – | – | – | – |
| 18 | WordNet path/IC similarity | ✓ | – | – | – | – | – | – | – | – | ✓ | ✓ | – |
| 19 | Synonym lookup | ✓ | – | – | – | – | – | – | – | – | – | – | – |
| 20 | Antonym lookup | ✓ | – | – | – | – | – | – | – | – | – | – | – |
| 21 | Hypernym/Hyponym lookup | ✓ | – | – | – | – | – | – | – | – | – | – | – |
| 22 | Topic-model (LSA/ESA) | – | – | – | – | – | – | – | – | – | – | ✓ | – |
| 23 | Structural/stylistic | – | – | – | – | – | – | – | – | – | – | ✓ | – |
| | **Raw coverage count** | **7** | **1** | **3** | **3** | **1** | **9** | **6** | **5** | **1** | **1** | **8** | **6** |

**Note on single-source families:** eight families have exactly one implementing
candidate: compression-based distance (8, textdistance only), fuzzy-extract (10,
RapidFuzz only), transformer embeddings (13, SBERT only), Word Mover's Distance (14,
gensim only), the contextual eval. metric (15, BERTScore only), cross-encoder
reranking (16, SBERT only), and synonym/antonym lookup (19, 20, NLTK only). Any
solution targeting 100% coverage must include the library behind each of these — the
optimization below only has real freedom in *how* it covers the remaining,
multiply-implemented families.

---

## 4. Quality weights

`Q(l) = freshness(l) × api_compat(l)`.

### 4.1 Freshness (recency of maintenance, 0–1)

| Library | Latest release | Freshness |
|---|---|---|
| RapidFuzz | v3.14.5 (7 Apr 2026), commits into Aug 2026 | 1.00 |
| scikit-learn | v1.9.0 (2026), steady quarterly cadence | 1.00 |
| sentence-transformers | v5.7.0 (6 Aug 2026), monthly+ cadence | 1.00 |
| NLTK | actively maintained, security-patch commits through Jul 2026 | 0.95 |
| spaCy | v3.8.14 (28 Mar 2026), regular patch cadence | 0.90 |
| gensim | v4.4.0 (16 Oct 2025) — ~10 months since last release, slower cadence | 0.75 |
| jellyfish | v1.2.1 — infrequent but steady releases | 0.70 |
| WS4J | active fork (dmeoli/WS4J), but underlying algorithm code essentially frozen since its ~2013 port | 0.40 |
| py_stringmatching | low activity, no recent major releases | 0.35 |
| textdistance | v4.6.3 (16 Jul 2024) — no release in 24+ months | 0.30 |
| BERTScore | v0.3.13 — no release in 12+ months, flagged inactive by Snyk | 0.30 |
| DKPro Similarity | low recent commit activity, largely legacy | 0.25 |

### 4.2 API compatibility (fit for a unified, Python-first, containerized microservice, 0–1)

Criteria: native return type (score/tensor vs. Java in-place object), ease of
pip/container packaging, native-dependency footprint, and runtime match with the rest
of the (assumed Python) stack.

| Library | Paradigm | Packaging | api_compat |
|---|---|---|---|
| scikit-learn | Returns ndarray, pure Python API | Trivial (`pip install scikit-learn`), no heavy runtime deps | 1.00 |
| textdistance | Returns float/int, pure Python | Trivial, zero required deps | 1.00 |
| RapidFuzz | Returns float/int, C++ core via prebuilt wheels | Trivial pip install | 0.95 |
| jellyfish | Returns str/int/float, Rust core via prebuilt wheels | Trivial pip install | 0.95 |
| NLTK | Returns Python objects (Synset, list, float) | Easy, but needs a one-time corpus download (`nltk.download`) | 0.90 |
| spaCy | Returns float, Python/Cython | Easy, but needs a model download | 0.90 |
| gensim | Returns ndarray/float, Python/Cython | Easy, numpy/scipy dependency | 0.85 |
| sentence-transformers | Returns ndarray/Tensor, pure Python over PyTorch | Easy, but heavier model-download/GPU footprint | 0.85 |
| py_stringmatching | Returns float, pure Python | Easy, but less polished/consistent API surface | 0.80 |
| BERTScore | Returns Tensor triple, pure Python over PyTorch | Needs model download, GPU strongly recommended | 0.75 |
| WS4J | Returns `Relatedness` object, Java | Needs a JVM sidecar / Py4J-style bridge inside a Python-first container | 0.30 |
| DKPro Similarity | Returns double, Java + Apache UIMA | Heavy XML/UIMA configuration, JVM sidecar required, no PyPI path at all | 0.20 |

### 4.3 Combined weight `Q(l)`

| Library | Freshness | api_compat | **Q(l)** |
|---|---|---|---|
| scikit-learn | 1.00 | 1.00 | **1.000** |
| RapidFuzz | 1.00 | 0.95 | **0.950** |
| NLTK | 0.95 | 0.90 | **0.855** |
| sentence-transformers | 1.00 | 0.85 | **0.850** |
| spaCy | 0.90 | 0.90 | **0.810** |
| jellyfish | 0.70 | 0.95 | **0.665** |
| gensim | 0.75 | 0.85 | **0.638** |
| py_stringmatching | 0.35 | 0.80 | **0.280** |
| textdistance | 0.30 | 1.00 | **0.300** |
| BERTScore | 0.30 | 0.75 | **0.225** |
| WS4J | 0.40 | 0.30 | **0.120** |
| DKPro Similarity | 0.25 | 0.20 | **0.050** |

---

## 5. Greedy weighted maximum-coverage run

**Step 1** — pick the library maximizing `Q(l) × |cover(l)|`:

| Library | \|cover(l)\| | Q(l) | Score |
|---|---|---|---|
| **NLTK** | 7 | 0.855 | **5.985 ← selected** |
| RapidFuzz | 6 | 0.950 | 5.700 |
| jellyfish | 5 | 0.665 | 3.325 |
| textdistance | 9 | 0.300 | 2.700 |
| sentence-transformers | 3 | 0.850 | 2.550 |
| gensim | 3 | 0.638 | 1.914 |
| py_stringmatching | 6 | 0.280 | 1.680 |
| scikit-learn | 1 | 1.000 | 1.000 |
| spaCy | 1 | 0.810 | 0.810 |
| DKPro Similarity | 8 | 0.050 | 0.400 |
| BERTScore | 1 | 0.225 | 0.225 |
| WS4J | 1 | 0.120 | 0.120 |

→ **Selected: NLTK** (covers 1, 2, 6, 18, 19, 20, 21 → 7/23, 30%)

**Step 2** — recompute `new(l, S)` against the 16 remaining families:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **RapidFuzz** | 3, 4, 5, 10 | 4 | 0.950 | **3.800 ← selected** |
| jellyfish | 3, 4, 9 | 3 | 0.665 | 1.995 |
| sentence-transformers | 13, 16, 17 | 3 | 0.850 | 2.550 |
| textdistance | 3, 4, 5, 7, 8, 9 | 6 | 0.300 | 1.800 |
| gensim | 12, 14, 17 | 3 | 0.638 | 1.914 |
| py_stringmatching | 3, 7, 9, 11 | 4 | 0.280 | 1.120 |
| scikit-learn | 11 | 1 | 1.000 | 1.000 |
| spaCy | 12 | 1 | 0.810 | 0.810 |
| DKPro Similarity | 3, 5, 9, 11, 22, 23 | 6 | 0.050 | 0.300 |
| BERTScore | 15 | 1 | 0.225 | 0.225 |
| WS4J | — | 0 | 0.120 | 0.000 |

→ **Selected: RapidFuzz** (adds Jaro/Jaro-Winkler, Hamming, LCS, fuzzy-extract → 11/23, 48%)

**Step 3** — remaining: {7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 22, 23}:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **sentence-transformers** | 13, 16, 17 | 3 | 0.850 | **2.550 ← selected** |
| gensim | 12, 14, 17 | 3 | 0.638 | 1.914 |
| textdistance | 7, 8, 9 | 3 | 0.300 | 0.900 |
| py_stringmatching | 7, 9, 11 | 3 | 0.280 | 0.840 |
| scikit-learn | 11 | 1 | 1.000 | 1.000 |
| jellyfish | 9 | 1 | 0.665 | 0.665 |
| spaCy | 12 | 1 | 0.810 | 0.810 |
| DKPro Similarity | 9, 11, 22, 23 | 4 | 0.050 | 0.200 |
| BERTScore | 15 | 1 | 0.225 | 0.225 |

→ **Selected: sentence-transformers** (adds transformer sentence embeddings, cross-encoder reranking, semantic search → 14/23, 61%)

**Step 4** — remaining: {7, 8, 9, 11, 12, 14, 15, 22, 23}:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **gensim** | 12, 14 | 2 | 0.638 | **1.276 ← selected** |
| scikit-learn | 11 | 1 | 1.000 | 1.000 |
| textdistance | 7, 8, 9 | 3 | 0.300 | 0.900 |
| py_stringmatching | 7, 9, 11 | 3 | 0.280 | 0.840 |
| jellyfish | 9 | 1 | 0.665 | 0.665 |
| spaCy | 12 | 1 | 0.810 | 0.810 |
| DKPro Similarity | 9, 11, 22, 23 | 4 | 0.050 | 0.200 |
| BERTScore | 15 | 1 | 0.225 | 0.225 |

→ **Selected: gensim** (adds static word/doc embeddings, Word Mover's Distance → 16/23, 70%)

**Step 5** — remaining: {7, 8, 9, 11, 15, 22, 23}:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **scikit-learn** | 11 | 1 | 1.000 | **1.000 ← selected** |
| textdistance | 7, 8, 9 | 3 | 0.300 | 0.900 |
| py_stringmatching | 7, 9, 11 | 3 | 0.280 | 0.840 |
| jellyfish | 9 | 1 | 0.665 | 0.665 |
| DKPro Similarity | 9, 11, 22, 23 | 4 | 0.050 | 0.200 |
| BERTScore | 15 | 1 | 0.225 | 0.225 |

→ **Selected: scikit-learn** (adds TF-IDF vector-space cosine → 17/23, 74%)

**Step 6** — remaining: {7, 8, 9, 15, 22, 23}:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **textdistance** | 7, 8, 9 | 3 | 0.300 | **0.900 ← selected** |
| py_stringmatching | 7, 9 | 2 | 0.280 | 0.560 |
| jellyfish | 9 | 1 | 0.665 | 0.665 |
| DKPro Similarity | 9, 22, 23 | 3 | 0.050 | 0.150 |
| BERTScore | 15 | 1 | 0.225 | 0.225 |

→ **Selected: textdistance** (adds sequence alignment, compression-based distance, extra phonetic coverage → 20/23, 87%)

**Step 7** — remaining: {15, 22, 23}:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **BERTScore** | 15 | 1 | 0.225 | **0.225 ← selected** |
| DKPro Similarity | 22, 23 | 2 | 0.050 | 0.100 |

→ **Selected: BERTScore** (adds contextual-embedding evaluation metric → 21/23, 91%)

**Step 8** — remaining: {22, 23} — only DKPro Similarity covers either:

| Library | New families | \|new\| | Q(l) | Score |
|---|---|---|---|---|
| **DKPro Similarity** | 22, 23 | 2 | 0.050 | **0.100 ← only remaining contributor** |

→ **Selected: DKPro Similarity** (adds topic-model similarity, structural/stylistic measures → 23/23, 100%)

No further library adds coverage: spaCy, jellyfish, WS4J, and py_stringmatching are
now fully subsumed by the chosen set, so the algorithm terminates.

---

## 6. Recommendation

### Tier 1 — Minimal core set (recommended default)

| Rank | Library | New families added | Cumulative coverage | Q(l) |
|---|---|---|---|---|
| 1 | **NLTK** | 7 (edit distance, Damerau-Lev., token-set, WordNet similarity, synonym, antonym, hypernym/hyponym) | 7/23 (30%) | 0.855 |
| 2 | **RapidFuzz** | 4 (Jaro/Jaro-Winkler, Hamming, LCS, fuzzy-match/extract) | 11/23 (48%) | 0.950 |
| 3 | **sentence-transformers** | 3 (transformer sentence/doc embeddings, cross-encoder reranking, semantic search) | 14/23 (61%) | 0.850 |
| 4 | **gensim** | 2 (static word/doc embeddings, Word Mover's Distance) | 16/23 (70%) | 0.638 |

This 4-library set reaches **70%** family coverage with very low mutual overlap, and —
importantly — it covers **100% of the categories explicitly named in the original
requirements**: semantic similarity of words (gensim/spaCy-style vectors via gensim),
sentences and documents (sentence-transformers), plus synonym/antonym/hypernym lookup
(NLTK/WordNet), plus fast general-purpose string/fuzzy matching (RapidFuzz). All four
are actively maintained, expose clean Python object-return APIs (no JVM, no UIMA), and
have low native-dependency friction (NLTK: corpus download only; RapidFuzz: prebuilt
wheels; sentence-transformers/gensim: standard PyPI + numpy/PyTorch).

### Tier 2 — Broader string-algorithm coverage

| Rank | Library | New families added | Cumulative coverage | Q(l) |
|---|---|---|---|---|
| 5 | **scikit-learn** | 1 (TF-IDF vector-space cosine) | 17/23 (74%) | 1.000 |
| 6 | **textdistance** | 3 (sequence alignment, compression-based distance, extra phonetic algorithms) | 20/23 (87%) | 0.300 |

Add these two if you want classic TF-IDF-based document similarity (a common,
cheap, explainable baseline/fallback next to the transformer-based measures) and the
long tail of edit-distance variants (Needleman-Wunsch, Smith-Waterman, Gotoh,
compression-based NCD, Editex/MRA phonetics) that RapidFuzz and NLTK don't implement.
scikit-learn is an especially "free" addition: `Q(l) = 1.000`, trivial dependency
footprint, and no conflict with anything already in the stack.

### Tier 3 — Full-coverage completion

| Rank | Library | New families added | Cumulative coverage | Q(l) |
|---|---|---|---|---|
| 7 | **BERTScore** | 1 (contextual-embedding evaluation metric, P/R/F1) | 21/23 (91%) | 0.225 |
| 8 | **DKPro Similarity** | 2 (topic-model similarity: LSA/ESA; structural/stylistic measures) | 23/23 (100%) | 0.050 |

Add BERTScore only if you specifically need an evaluation-style semantic overlap
score (precision/recall/F1 over token alignments) as distinct from a single cosine
number — useful for scoring generated text against references, less useful for
generic pairwise similarity. Its low `Q(l)` reflects genuinely stale maintenance
(flagged inactive), so pin the version and treat it as a vendored dependency rather
than an actively-supported one.

Add DKPro Similarity only if LSA/ESA-style topic similarity or the structural/
stylistic measures (n-gram containment, type-token ratio, greedy string tiling) are
hard requirements. Its very low `api_compat` (0.20) reflects real operational cost:
no PyPI/pip path, an Apache UIMA + JVM stack that must be run as a separate sidecar
service behind the unified API, and low recent maintenance activity — mirroring how
`graph-tool` was treated as an isolated, optional component in the graph-generation
analysis. **Recommendation: isolate it in its own container** rather than embed it in
the same image as the Python libraries, or accept the 91% coverage from Tier 1+2+
BERTScore and skip it entirely.

### Explicitly excluded

| Library | Reason for exclusion |
|---|---|
| **PolyFuzz** | Orchestrates TF-IDF/RapidFuzz/embedding backends but implements no algorithm of its own — a priori exclusion, exactly analogous to `rigraph` wrapping `python-igraph`'s C core. |
| **python-Levenshtein** | Thin wrapper over RapidFuzz's own C core (same maintaining org) — zero net-new coverage. |
| **spaCy** | Its only family (12, static word/doc-embedding similarity) is fully subsumed once gensim is selected; spaCy also requires a separate model download and has no native lexical-relation API of its own (the `spacy-wordnet` extension exists but is a third-party add-on, not spaCy's own surface). |
| **scikit-learn's overlap partner, py_stringmatching** | After RapidFuzz, NLTK, textdistance, and scikit-learn are selected, every one of its families (1, 3, 6, 7, 9, 11) is already covered by a higher-`Q(l)` alternative. |
| **jellyfish** | Fast (Rust-backed) but every one of its families (1, 2, 3, 4, 9) is subsumed by RapidFuzz (1–4) and textdistance (9) once those are selected. Worth reconsidering only if profiling shows RapidFuzz's phonetic gap (jellyfish's Soundex/Metaphone/NYSIIS are slightly more complete than textdistance's Editex/MRA) matters for your specific workload. |
| **WS4J** | Its only family (18, WordNet path/IC similarity) is already covered by NLTK in pure Python; WS4J would only be worth adding in an all-Java stack, and its `api_compat` (0.30) reflects the JVM-sidecar cost of embedding it in a Python-first service. |

---

## 7. Residual gaps

Even with the full 8-library "complete" set, a few fine-grained items noted in the
original comparison are not exactly duplicated — they are treated as *depth within an
already-covered family*, not a missing family:

- **NLTK's Resnik/Jiang-Conrath/Lin similarity** require a precomputed WordNet
  Information Content corpus as an *operational* dependency (a data file, not just a
  pip package) — this is a deployment detail to plan for, not a coverage gap.
- **jellyfish's phonetic encodings** (Soundex, Metaphone, NYSIIS, Match Rating) are a
  slightly different, Rust-accelerated set than textdistance's phonetic-ish measures
  (Editex, MRA) — same family, different exact algorithm surface.
- **BERTScore's token-level greedy matching** is a genuinely different computation
  from sentence-transformers' plain cosine similarity, even though both are
  BERT-family models — kept as its own family (15) rather than folded into family 13
  for this reason.
- **DKPro's GreedyStringTiling** (plagiarism-detection-style structural similarity) is
  a distinctive algorithm even within family 23 — no other selected library
  reproduces its specific greedy-substring-matching approach.

These are considered acceptable trade-offs given the goal of minimizing the number of
embedded libraries.

---

## 8. Final answer

**Recommended library set (Tier 1): NLTK + RapidFuzz + sentence-transformers + gensim**
— 70% family coverage, 100% of the explicitly-requested categories (word/sentence/
document semantic similarity + synonym/antonym/hypernym), minimal overlap, all
actively maintained, all pure-Python-compatible (no JVM).

**If broader string-algorithm coverage is wanted:** add **scikit-learn +
textdistance** (Tier 2) → 87% coverage, still zero JVM dependencies.

**If 100% family coverage is a hard requirement:** add **BERTScore** (91%) and
**DKPro Similarity** as an isolated JVM sidecar (100%) — accepting DKPro's
significantly higher operational cost for the last 9 percentage points.