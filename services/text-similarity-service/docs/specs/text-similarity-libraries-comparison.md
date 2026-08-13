# Text-Similarity-Measures Libraries — Comparison

Overview of existing libraries for embedding text-similarity algorithms (word/sentence/document semantic similarity, string/edit distance, synonym/antonym/hypernym lookup) into a containerized microservice with a unified API. Compiled via web research; dates reflect the latest confirmed release/commit as of **mid-2026**.

---

## Summary

| Library | Language | Public repository | Latest release / maintained | Category |
|---|---|---|---|---|
| **spaCy** | Python/Cython | https://github.com/explosion/spaCy | v3.8.14 (28 Mar 2026), actively maintained | Word/doc vector similarity, tokenization, (via extension) WordNet |
| **NLTK** | Python | https://github.com/nltk/nltk | Actively maintained (security patches Jul 2026); stable line 3.9.x | WordNet synonym/antonym/hypernym, path/Wu-Palmer/Resnik/Lin/Jiang-Conrath similarity, string/edit distance |
| **gensim** | Python/Cython | https://github.com/RaRe-Technologies/gensim (mirror piskvorky/gensim) | v4.4.0 (16 Oct 2025) | Word2Vec/FastText/Doc2Vec embeddings, Word Mover's Distance, corpus similarity |
| **sentence-transformers (SBERT)** | Python | https://github.com/huggingface/sentence-transformers (moved from UKPLab; now HF-maintained) | v5.7.0 (6 Aug 2026), actively maintained | Sentence/document embeddings, semantic search, cross-encoder reranking, paraphrase mining |
| **scikit-learn** | Python/Cython | https://github.com/scikit-learn/scikit-learn | v1.9.0 (2026), actively maintained | TF-IDF vectorization + cosine/pairwise distance for docs |
| **textdistance** | Python (pure, optional C-lib backends) | https://github.com/life4/textdistance | v4.6.3 (16 Jul 2024) — no release in 12+ months, low activity | 30+ string-distance/similarity algorithms (edit, token, sequence, compression, phonetic) |
| **RapidFuzz** | Python bindings over C++ | https://github.com/rapidfuzz/RapidFuzz | v3.14.5 (7 Apr 2026), actively maintained (commits Aug 2026) | Fast fuzzy string matching, edit distances, batch/process matching |
| **jellyfish** | Python bindings over Rust (+pure-Python fallback) | https://github.com/jamesturk/jellyfish (canonical source now at codeberg.org/jpt/jellyfish) | v1.2.1, maintained | Edit distances + phonetic encoding (Soundex, Metaphone, NYSIIS) |
| **python-Levenshtein / Levenshtein** | Python bindings over C | https://github.com/rapidfuzz/python-Levenshtein | Actively maintained (commits Aug 2026), now under RapidFuzz org | Levenshtein distance/ratio (legacy API, thin wrapper over RapidFuzz's C core) |
| **PolyFuzz** | Python | https://github.com/MaartenGr/PolyFuzz | Maintained, sporadic releases | Wrapper unifying TF-IDF, edit-distance, embedding (FastText/GloVe/HF/SBERT) backends behind one `.match()` API |
| **BERTScore** | Python (PyTorch) | https://github.com/Tiiiger/bert_score | v0.3.13 — inactive (no release in 12+ months), still widely used | Contextual-embedding-based semantic similarity/evaluation metric (P/R/F1) |
| **WS4J** (WordNet Similarity for Java) | Java | https://github.com/dmeoli/WS4J (active fork; original hidekishima repo unmaintained since Google Code import) | Fork actively updated; original core dates to ~2013 algorithmically | WordNet-based word semantic relatedness (Path, WUP, LCH, Resnik, JCN, Lin, HSO, Lesk) |
| **DKPro Similarity** | Java (Apache UIMA-based) | https://github.com/dkpro/dkpro-similarity | Low recent commit activity — largely legacy but very broad | Large catalog: string/n-gram, ESA, LSA, structural, stylistic, phonetic, WordNet-based text similarity |
| **py_stringmatching** | Python | https://github.com/anhaidgroup/py_stringmatching | Low activity, stable | Broad catalog of string-similarity measures for entity matching (affine, editex, jaro, soft TF-IDF, etc.) |

---

## Per-library details

### NLTK (Python) — WordNet + string metrics
Repo: https://github.com/nltk/nltk · Requires the `wordnet` and `omw-1.4` NLTK data packages (`nltk.download('wordnet')`).

**WordNet lexical relations** (`nltk.corpus.wordnet`, conventionally imported `as wn`)

| Algorithm | Signature | Returns |
|---|---|---|
| Get synsets (senses) | `wn.synsets(lemma: str, pos: str=None, lang: str='eng') -> list[Synset]` | list of `Synset` |
| Synonyms | `synset.lemma_names(lang='eng') -> list[str]` (aggregate across `wn.synsets(word)` for all synonyms of a word) | `list[str]` |
| Antonyms | `lemma.antonyms() -> list[Lemma]` (called on a `Synset.lemmas()` element) | `list[Lemma]` |
| Hypernyms (is-a, broader) | `synset.hypernyms() -> list[Synset]` | `list[Synset]` |
| Hyponyms (is-a, narrower) | `synset.hyponyms() -> list[Synset]` | `list[Synset]` |
| Holonyms / Meronyms | `synset.part_holonyms()`, `synset.member_holonyms()`, `synset.part_meronyms()` etc. `-> list[Synset]` | `list[Synset]` |
| Path similarity | `synset.path_similarity(other: Synset, simulate_root=True) -> float \| None` | float in (0,1] |
| Wu-Palmer similarity | `synset.wup_similarity(other: Synset, simulate_root=True) -> float \| None` | float in (0,1] |
| Leacock-Chodorow similarity | `synset.lch_similarity(other: Synset, simulate_root=True) -> float \| None` | float |
| Resnik similarity (needs Information Content corpus) | `synset.res_similarity(other: Synset, ic: dict) -> float` | float |
| Jiang-Conrath similarity | `synset.jcn_similarity(other: Synset, ic: dict) -> float` | float |
| Lin similarity | `synset.lin_similarity(other: Synset, ic: dict) -> float` | float |

**String/edit-distance metrics** (`nltk.metrics.distance`)

| Algorithm | Signature | Returns |
|---|---|---|
| Levenshtein edit distance | `nltk.edit_distance(s1: str, s2: str, substitution_cost: int=1, transpositions: bool=False) -> int` | `int` |
| Jaccard distance | `nltk.jaccard_distance(label1: frozenset, label2: frozenset) -> float` | `float` |
| MASI distance | `nltk.masi_distance(label1: frozenset, label2: frozenset) -> float` | `float` |
| Binary distance | `nltk.binary_distance(label1, label2) -> float` | `float` |

---

### spaCy (Python/Cython) — vector-based similarity
Repo: https://github.com/explosion/spaCy · v3.8.14 (Mar 2026). Note: similarity requires a pipeline with real word vectors (`en_core_web_md`/`lg`), not the default transformer-only `sm`/`trf` pipelines.

| Algorithm | Signature | Returns |
|---|---|---|
| Doc-to-Doc/Span/Token similarity | `Doc.similarity(other: Doc \| Span \| Token) -> float` | cosine similarity, float in [-1,1] |
| Span similarity | `Span.similarity(other: Doc \| Span \| Token) -> float` | float |
| Token similarity | `Token.similarity(other: Doc \| Span \| Token) -> float` | float |
| Raw word vector access | `Token.vector -> numpy.ndarray[float32]` | vector |
| Has vector? | `Token.has_vector -> bool` | bool |

**Synonym/antonym/hypernym via extension**: spaCy itself has no lexical-relation API; the community pipeline component **spacy-wordnet** (https://github.com/recognai/spacy-wordnet) bridges spaCy tokens to NLTK's WordNet:
`token._.wordnet.synsets() -> list[Synset]`, `token._.wordnet.lemmas() -> list[Lemma]`, `token._.wordnet.wordnet_domains() -> list[str]`.

---

### gensim (Python/Cython) — embeddings & corpus similarity
Repo: https://github.com/RaRe-Technologies/gensim · v4.4.0 (Oct 2025).

| Algorithm | Signature | Returns |
|---|---|---|
| Train Word2Vec | `gensim.models.Word2Vec(sentences=None, vector_size=100, window=5, min_count=5, sg=0, workers=3, epochs=5) -> Word2Vec` | model |
| Word similarity | `KeyedVectors.similarity(w1: str, w2: str) -> float` | float |
| Most similar words | `KeyedVectors.most_similar(positive: list[str]=None, negative: list[str]=None, topn: int=10) -> list[tuple[str,float]]` | list of (word, score) |
| Set-of-words similarity | `KeyedVectors.n_similarity(ws1: list[str], ws2: list[str]) -> float` | float |
| Word Mover's Distance | `KeyedVectors.wmdistance(document1: list[str], document2: list[str]) -> float` | float (lower = more similar) |
| Train Doc2Vec | `gensim.models.doc2vec.Doc2Vec(documents=None, vector_size=100, min_count=2, epochs=40) -> Doc2Vec` | model |
| Infer doc vector | `Doc2Vec.infer_vector(doc_words: list[str]) -> numpy.ndarray` | vector |
| Train FastText (handles OOV/subwords) | `gensim.models.FastText(sentences=None, vector_size=100, window=5, min_count=5) -> FastText` | model |
| Corpus similarity index (cosine) | `gensim.similarities.MatrixSimilarity(corpus, num_features) -> index`; `index[query_bow] -> numpy.ndarray[float]` | similarity scores |
| WMD-based corpus index | `gensim.similarities.WmdSimilarity(corpus: list[list[str]], w2v_model, num_best: int=None) -> index`; `index[query] -> list[tuple[int,float]]` | ranked (doc_id, score) |
| Soft cosine similarity | `gensim.similarities.SoftCosineSimilarity(corpus, similarity_matrix) -> index` | index |

---

### sentence-transformers / SBERT (Python) — semantic sentence & document similarity
Repo: https://github.com/huggingface/sentence-transformers · v5.7.0 (6 Aug 2026). Now maintained by Hugging Face (originally UKP Lab / Nils Reimers).

| Algorithm | Signature | Returns |
|---|---|---|
| Load model | `SentenceTransformer(model_name_or_path: str, device: str=None) -> SentenceTransformer` | model |
| Encode text(s) | `model.encode(sentences: str \| list[str], batch_size: int=32, convert_to_tensor: bool=False, normalize_embeddings: bool=False) -> numpy.ndarray \| torch.Tensor` | embedding(s) |
| Cosine similarity | `sentence_transformers.util.cos_sim(a: Tensor, b: Tensor) -> Tensor` | pairwise similarity matrix |
| Dot-product score | `sentence_transformers.util.dot_score(a: Tensor, b: Tensor) -> Tensor` | matrix |
| Semantic search (top-k retrieval) | `util.semantic_search(query_embeddings, corpus_embeddings, top_k: int=10) -> list[list[dict]]` | ranked hits with `corpus_id`, `score` |
| Paraphrase mining in a corpus | `util.paraphrase_mining(model, sentences: list[str], batch_size=32) -> list[list[float,int,int]]` | list of `[score, i, j]` |
| Cross-encoder reranking (pairwise) | `CrossEncoder(model_name: str).predict(sentences: list[tuple[str,str]]) -> numpy.ndarray[float]` | relevance/similarity scores |

---

### scikit-learn (Python/Cython) — classic vector-space similarity
Repo: https://github.com/scikit-learn/scikit-learn · v1.9.0 (2026).

| Algorithm | Signature | Returns |
|---|---|---|
| TF-IDF vectorization | `sklearn.feature_extraction.text.TfidfVectorizer(...).fit_transform(raw_documents: list[str]) -> scipy.sparse.csr_matrix` | doc-term matrix |
| Cosine similarity | `sklearn.metrics.pairwise.cosine_similarity(X, Y=None) -> numpy.ndarray` | similarity matrix |
| Pairwise distances (generic) | `sklearn.metrics.pairwise_distances(X, Y=None, metric='euclidean') -> numpy.ndarray` | distance matrix |
| Euclidean / Manhattan distance | `sklearn.metrics.pairwise.euclidean_distances(X, Y=None)`, `manhattan_distances(X, Y=None) -> numpy.ndarray` | distance matrix |

---

### textdistance (Python, pure + optional external-lib acceleration)
Repo: https://github.com/life4/textdistance · v4.6.3 (Jul 2024). Common interface across ~30 algorithms: each is a callable/class with `.distance(*sequences)`, `.similarity(*sequences)`, `.normalized_distance(*sequences) -> float [0,1]`, `.normalized_similarity(*sequences) -> float [0,1]`.

| Family | Algorithms included | Signature pattern |
|---|---|---|
| Edit-based | Levenshtein, Damerau-Levenshtein, Jaro, Jaro-Winkler, Needleman-Wunsch, Gotoh, Smith-Waterman, StrCmp95, Hamming, MLIPNS | `textdistance.levenshtein(s1: str, s2: str) -> int`; `textdistance.levenshtein.normalized_similarity(s1, s2) -> float` |
| Token-based | Jaccard, Sørensen-Dice, Tversky, Overlap, Cosine, Monge-Elkan, Bag | `textdistance.jaccard(seq1: Iterable, seq2: Iterable) -> float` |
| Sequence-based | Longest Common Subsequence, Longest Common Substring, Ratcliff-Obershelp | `textdistance.lcsseq(s1, s2) -> str`; `textdistance.ratcliff_obershelp.normalized_similarity(s1,s2) -> float` |
| Compression-based | Arithmetic NCD, RLE NCD, BWT-RLE NCD, √-NCD, Entropy NCD | `textdistance.entropy_ncd(s1, s2) -> float` |
| Phonetic/misc | Editex, MRA, Prefix, Postfix, Length, Identity | `textdistance.editex(s1, s2) -> int` |

---

### RapidFuzz (Python bindings over C++) — fast fuzzy matching
Repo: https://github.com/rapidfuzz/RapidFuzz · v3.14.5 (Apr 2026), actively maintained.

| Algorithm | Signature | Returns |
|---|---|---|
| Simple ratio | `rapidfuzz.fuzz.ratio(s1: str, s2: str, processor=None, score_cutoff: float=None) -> float` | 0–100 |
| Partial ratio | `fuzz.partial_ratio(s1: str, s2: str, ...) -> float` | 0–100 |
| Token sort ratio | `fuzz.token_sort_ratio(s1: str, s2: str, ...) -> float` | 0–100 |
| Token set ratio | `fuzz.token_set_ratio(s1: str, s2: str, ...) -> float` | 0–100 |
| Weighted ratio | `fuzz.WRatio(s1: str, s2: str, ...) -> float` | 0–100 |
| Levenshtein distance | `rapidfuzz.distance.Levenshtein.distance(s1: str, s2: str, weights=(1,1,1), score_cutoff=None) -> int` | int |
| Normalized similarity (any metric) | `rapidfuzz.distance.<Metric>.normalized_similarity(s1, s2) -> float` (Metric ∈ {Levenshtein, DamerauLevenshtein, Indel, Hamming, Jaro, JaroWinkler, OSA, LCSseq}) | 0–1 |
| Batch best-match extraction | `rapidfuzz.process.extract(query: str, choices: Iterable[str], scorer=fuzz.WRatio, limit: int=5) -> list[tuple[str,float,int]]` | ranked matches |
| Single best match | `process.extractOne(query: str, choices, scorer=fuzz.WRatio, score_cutoff=None) -> tuple[str,float,int] \| None` | best match |

---

### jellyfish (Python bindings over Rust, pure-Python fallback)
Repo: https://github.com/jamesturk/jellyfish · v1.2.1.

| Algorithm | Signature | Returns |
|---|---|---|
| Levenshtein distance | `jellyfish.levenshtein_distance(s1: str, s2: str) -> int` | int |
| Damerau-Levenshtein distance | `jellyfish.damerau_levenshtein_distance(s1: str, s2: str) -> int` | int |
| Jaro similarity | `jellyfish.jaro_similarity(s1: str, s2: str) -> float` | 0–1 |
| Jaro-Winkler similarity | `jellyfish.jaro_winkler_similarity(s1: str, s2: str, long_tolerance: bool=False) -> float` | 0–1 |
| Hamming distance | `jellyfish.hamming_distance(s1: str, s2: str) -> int` | int |
| Match Rating comparison | `jellyfish.match_rating_comparison(s1: str, s2: str) -> bool \| None` | bool |
| Soundex phonetic code | `jellyfish.soundex(s: str) -> str` | code |
| Metaphone phonetic code | `jellyfish.metaphone(s: str) -> str` | code |
| NYSIIS phonetic code | `jellyfish.nysiis(s: str) -> str` | code |

---

### PolyFuzz (Python) — multi-backend fuzzy matcher
Repo: https://github.com/MaartenGr/PolyFuzz. Unifies TF-IDF, RapidFuzz edit-distance, FastText/GloVe embeddings, and 🤗 Transformers/SBERT embeddings behind one interface.

| Algorithm | Signature | Returns |
|---|---|---|
| Build matcher | `PolyFuzz(method: str \| list = "TF-IDF")` (method ∈ {"TF-IDF","EditDistance","Embeddings", custom model list}) | instance |
| Match two lists | `.match(from_list: list[str], to_list: list[str]=None) -> self` (populates internal results) | self |
| Get matches | `.get_matches() -> pandas.DataFrame` (columns: `From`, `To`, `Similarity`) | DataFrame |
| Group near-duplicate matches | `.group(link_min_similarity: float=0.75) -> self` | self |

---

### BERTScore (Python, PyTorch) — contextual-embedding semantic similarity
Repo: https://github.com/Tiiiger/bert_score · v0.3.13 (inactive but widely used as an evaluation metric).

| Algorithm | Signature | Returns |
|---|---|---|
| Score candidate vs. reference(s) | `bert_score.score(cands: list[str], refs: list[str] \| list[list[str]], model_type: str=None, lang: str=None, idf: bool=False, batch_size: int=64, rescale_with_baseline: bool=False) -> tuple[Tensor, Tensor, Tensor]` | `(Precision, Recall, F1)` tensors, each in [0,1] |
| Reusable scorer object | `bert_score.BERTScorer(model_type=None, lang=None, rescale_with_baseline=False).score(cands, refs) -> tuple[Tensor,Tensor,Tensor]` | `(P, R, F1)` |

---

### WS4J — WordNet Similarity for Java
Repo (active fork): https://github.com/dmeoli/WS4J · uses Princeton WordNet 3.0 via MIT JWI. Reimplements the classic Perl `WordNet::Similarity`.

| Algorithm | Class / call pattern | Returns |
|---|---|---|
| Path measure | `new Path(db: ILexicalDatabase).calcRelatednessOfWords(word1: String, word2: String) -> Relatedness` | `Relatedness.getScore(): double` |
| Wu & Palmer | `new WuPalmer(db).calcRelatednessOfWords(String, String) -> Relatedness` | double via `.getScore()` |
| Leacock & Chodorow | `new LeacockChodorow(db).calcRelatednessOfWords(...)` | double |
| Resnik (needs IC) | `new Resnik(db).calcRelatednessOfWords(...)` | double |
| Jiang & Conrath | `new JiangConrath(db).calcRelatednessOfWords(...)` | double |
| Lin | `new Lin(db).calcRelatednessOfWords(...)` | double |
| Hirst & St-Onge | `new HirstStOnge(db).calcRelatednessOfWords(...)` | double |
| Lesk (gloss overlap) | `new Lesk(db).calcRelatednessOfWords(...)` | double |

---

### DKPro Similarity (Java, Apache UIMA)
Repo: https://github.com/dkpro/dkpro-similarity · broadest single catalog of *text* (not just word) similarity measures, but low recent commit activity.

| Category | Representative classes | Interface method |
|---|---|---|
| String/character | `CosineSimilarity`, `LongestCommonSubstringComparator`, `GreedyStringTiling`, `JaroSecondStringComparator` | `double getSimilarity(String[] s1, String[] s2)` |
| Word n-gram | `WordNGramJaccardMeasure(int n)`, `WordNGramContainmentMeasure(int n)` | `double getSimilarity(String[] s1, String[] s2)` |
| Vector-space/topic | `LatentSemanticAnalysis` (S-Space backed), `VectorIndexSourceRelatednessResource` (Explicit Semantic Analysis) | `double getSimilarity(...)` |
| WordNet-based | `WordNetComparator` (wraps Resnik/Lin/JCN/Path-style measures over WordNet) | `double getSimilarity(...)` |
| Structural/stylistic | Type-token ratio, stopword n-gram containment | `double getSimilarity(...)` |

---

### py_stringmatching (Python)
Repo: https://github.com/anhaidgroup/py_stringmatching. Broad catalog aimed at entity-resolution/record-linkage use cases.

| Family | Example classes | Signature pattern |
|---|---|---|
| Edit-distance | `Levenshtein()`, `Affine()`, `NeedlemanWunsch()`, `SmithWaterman()`, `Jaro()`, `JaroWinkler()` | `.get_raw_score(s1: str, s2: str) -> float`; `.get_sim_score(s1, s2) -> float` |
| Token-based | `Jaccard()`, `Cosine()`, `Dice()`, `OverlapCoefficient()`, `TfIdf()`, `SoftTfIdf()` | `.get_sim_score(bag1: list[str], bag2: list[str]) -> float` |
| Phonetic | `Soundex()`, `Editex()` | `.get_raw_score(s1, s2) -> float \| int` |

---

## Recommendations for a unified microservice

- **Primary semantic engine:** sentence-transformers (SBERT) for sentence/document-level semantic similarity, semantic search, and cross-encoder reranking — it's the most actively maintained and highest-quality option for embeddings today, with a huge model zoo on Hugging Face.
- **Word-level semantics + lexical relations:** NLTK + WordNet for synonym/antonym/hypernym/hyponym lookups and classic WordNet similarity measures (path, Wu-Palmer, Resnik, Lin, Jiang-Conrath) — the only Python library with a first-class synonym/antonym API out of the box.
- **String/edit-distance layer:** RapidFuzz for anything performance-sensitive (it's a fast C++ core with a Python fallback and is the most actively maintained string-matching library); fall back to textdistance if you need one of its ~30 exotic algorithms (compression-based, phonetic, sequence-based) that RapidFuzz doesn't cover.
- **Classic vector-space / TF-IDF baseline:** scikit-learn's `TfidfVectorizer` + `cosine_similarity` — cheap, dependency-light, good baseline/fallback when transformer models are overkill.
- **Word/document embeddings without transformers:** gensim (Word2Vec/FastText/Doc2Vec + Word Mover's Distance) — useful for domain-specific embeddings trained on your own corpus, or WMD as a complementary distance metric.
- **Evaluation-style semantic scoring:** BERTScore when you need a P/R/F1-style semantic overlap score (e.g., comparing generated text against a reference) rather than a single similarity number.
- **Java-native shop:** WS4J for WordNet-based word relatedness and DKPro Similarity if you want the broadest single catalog of Java text-similarity measures (structural, stylistic, LSA/ESA, WordNet-based) in one framework — at the cost of being UIMA-heavy and less actively maintained.
- **Multi-backend fuzzy matching UX:** PolyFuzz is a good reference implementation for exactly the kind of "unified API over several backends" you're building — worth reading its source even if you don't depend on it directly.

### Design implication for the unified API

These libraries disagree on:
- **Score direction & range** — some return *distance* (0 = identical), others *similarity* (1 = identical, or 0–100 for RapidFuzz's `fuzz` module).
- **Input granularity** — some operate on raw strings, others on token lists/bags, others on pre-trained vectors/embeddings.
- **Symmetry & normalization** — not all measures are symmetric or bounded to [0,1] by default (e.g., NLTK's `lch_similarity`, gensim's `wmdistance`).
- **Statefulness** — TF-IDF/embedding-based methods require a fit/encode step and model loading, while edit-distance methods are stateless pure functions.

A normalization layer should:
1. Map a canonical **measure name** (e.g. `levenshtein`, `jaro_winkler`, `cosine_tfidf`, `sbert_cosine`, `wordnet_wup`, `word2vec_cosine`, `wmd`, `bertscore_f1`) plus a canonical **granularity** (`char`, `token`, `word`, `sentence`, `document`) to the right backend call.
2. Normalize all outputs to a **similarity** score in `[0, 1]` (converting RapidFuzz's 0–100 scale, inverting distance metrics, and re-scaling unbounded scores like `lch_similarity`).
3. Cache loaded models (SBERT/gensim/spaCy vectors, WordNet IC files) as singletons in the service, since these are expensive to load per-request.
4. Expose a separate `/lexical-relations` endpoint (synonyms/antonyms/hypernyms/hyponyms) backed by NLTK WordNet (or WS4J/JWI in a JVM sidecar), since this is a fundamentally different operation (graph lookup, not a numeric score) from the similarity endpoints.