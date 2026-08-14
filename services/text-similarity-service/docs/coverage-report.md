# Coverage Report — Semantic Text Similarity, 16/16 Families

Maps the current service catalog (`GET /v1/similarity/text/algorithms`) to the 16 algorithm
families and their verification status via the compute endpoints
(`POST /v1/similarity/text/distance`, `POST /v1/similarity/text/retrieval`, `POST /v1/similarity/text/lexical`).

| # | Family | Algorithm | Operation | Backend | Extra / Status |
|---|---|---|---|---|---|
| 1 | WordNet path/IC similarity | `wordnet_similarity` | similarity | nltk (default) | base ✅ |
| 2 | Synonym lookup | `synonym` | lexical_relations | nltk (default), **odenet** (de) | base / `[de]` ✅ |
| 3 | Antonym lookup | `antonym` | lexical_relations | nltk (default), **odenet** (de) | base / `[de]` ✅ |
| 4 | Hypernym lookup | `hypernym` | lexical_relations | nltk (default), **odenet** (de) | base / `[de]` ✅ |
| 5 | Hyponym lookup | `hyponym` | lexical_relations | nltk (default), **odenet** (de) | base / `[de]` ✅ |
| 6 | TF-IDF vector-space cosine | `tfidf_cosine` | similarity | sklearn (default) | base ✅ |
| 7 | Token-set overlap (Jaccard/Dice) | `token_set_overlap` | similarity | builtin — variants `jaccard` / `dice` | base ✅ |
| 8 | BM25 lexical retrieval | `bm25` | retrieval | builtin | base ✅ |
| 9 | Semantic search / NN retrieval | `semantic_search` | retrieval | sentence-transformers | `[model]` ⏳ |
| 10 | Static word/doc embedding | `embedding_cosine` | similarity | gensim — variants `glove` / `fasttext` (local); `conceptnet_numberbatch` **two backends** (`local` gensim / `remote` api.conceptnet.io, default) | base ✅ (glove + numberbatch-remote automatic; fasttext + numberbatch-local gate-optional) |
| 11 | Transformer sentence embedding | `sbert_cosine` | similarity | sentence-transformers | `[model]` ⏳ |
| 12 | Word Mover's Distance | `wmd` | similarity | gensim | base ✅ (GloVe ~200 MB download, automatic) |
| 13 | Contextual eval metric (BERTScore) | `bertscore` | similarity | bert-score | `[model]` ⏳ |
| 14 | Cross-encoder reranking | `cross_encoder` | similarity | sentence-transformers | `[model]` ⏳ |
| 15 | Topic-model (LSA/ESA) | `topic_model` | similarity | dkpro (Java sidecar) | optional sidecar ✅ (routed, mocked) |
| 16 | Structural/stylistic | `structural_stylistic` | similarity | dkpro (Java sidecar) | optional sidecar ✅ (routed, mocked) |

## Legacy aliases

`jaccard` and `dice` are **not** separate families — they are legacy alias
algorithm names for family 7 (`token_set_overlap`) with the variant pinned
(`alias_of` / `fixed_variant` in the catalog). They remain listed in
`/v1/similarity/text/algorithms` so existing consumers keep working unchanged.

## Legend

- ✅ — verified end-to-end in the CI test suite
- ⏳ — requires the `[model]` extra (PyTorch / large model download); covered by
  `@pytest.mark.model_download` tests, skipped by default
- (routed, mocked) — computation is proxied to the Java sidecar; routing and
  envelope normalization are tested with a mocked sidecar (the real DKPro
  sidecar requires building DKPro Similarity from source, which is not
  feasible in CI)

## Optional DKPro Backend Extensions

These add no new family coverage — they are alternative implementations of
already-covered families, routed to the sidecar when `backend: "dkpro"` is
requested. The routing/failure behavior is tested; the DKPro implementations
themselves are placeholders until the DKPro library is built from source.

| Tag | DKPro class | Status |
|---|---|---|
| `tfidf_cosine` | `CosineSimilarity` | ✅ routed + tested |
| `wordnet_similarity` | `WordNetComparator` | ✅ routed + tested |

## Summary

- **16/16 families covered** by the API contract (10 base + 4 `[model]` + 2 DKPro)
- **10/16 verified end-to-end** in the default CI test run (base families 1–8, 10, 12)
- **4/16 covered by model-download tests** (families 9, 11, 13, 14, `[model]` extra)
- Families 15–16 are routed to the DKPro Java sidecar (tested with a mock)
- 2 optional DKPro backend extensions registered and routed
- 2 legacy aliases (`jaccard`, `dice`) map to `token_set_overlap`
