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
| 10 | Static word/doc embedding | `embedding_cosine` | similarity | gensim — variants `glove` / `fasttext` (local); `conceptnet_numberbatch` **two backends** (`local` sidecar / `remote` api.conceptnet.io, default) | base ✅ (glove + numberbatch-remote automatic; fasttext + numberbatch-local gate-optional) |
| 11 | Transformer sentence embedding | `sbert_cosine` | similarity | sentence-transformers | `[model]` ⏳ |
| 12 | Word Mover's Distance | `wmd` | similarity | gensim | base ✅ (GloVe ~200 MB download, automatic) |
| 13 | Contextual eval metric (BERTScore) | `bertscore` | similarity | bert-score | `[model]` ⏳ |
| 14 | Cross-encoder reranking | `cross_encoder` | similarity | sentence-transformers | `[model]` ⏳ |
| 15 | Topic-model (corpus-free LSI) | `topic_model` | similarity | builtin — variants `lsa` / `esa` | base ✅ |
| 16 | Structural/stylistic | `structural_stylistic` | similarity | builtin — n-gram containment / type-token ratio / greedy string tiling | base ✅ |

## Legacy aliases

`jaccard` and `dice` are **not** separate families — they are legacy alias
algorithm names for family 7 (`token_set_overlap`) with the variant pinned
(`alias_of` / `fixed_variant` in the catalog). They remain listed in
`/v1/similarity/text/algorithms` so existing consumers keep working unchanged.

## Legend

- ✅ — verified end-to-end in the CI test suite
- ⏳ — requires the `[model]` extra (PyTorch / large model download); covered by
  `@pytest.mark.model_download` tests, skipped by default

## Notes

- **Families 15–16 are now native, in-process measures.** The former DKPro Java
  sidecar has been removed: `topic_model` derives a latent space from the two
  input documents (TF-IDF + truncated SVD) and `structural_stylistic`
  implements n-gram containment, type-token ratio and greedy string tiling in
  pure Python. Neither needs an external model, a trained corpus or a separator
  JVM, so both run in the base `cpu` build and are end-to-end tested.

## Summary

- **16/16 families covered** by the API contract (12 base + 4 `[model]`)
- **12/16 verified end-to-end** in the default CI test run (base families 1–8, 10, 12, 15–16)
- **4/16 covered by model-download tests** (families 9, 11, 13, 14, `[model]` extra)
- 2 legacy aliases (`jaccard`, `dice`) map to `token_set_overlap`
