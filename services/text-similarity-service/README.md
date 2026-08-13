# text-similarity-service

**Semantic text similarity service** — measures how *similar the meaning* of
words, sentences and documents is, and looks up lexical relations
(synonym/antonym/hypernym). 13 algorithm families over 6 backends
(NLTK, sentence-transformers, gensim, scikit-learn, BERTScore,
DKPro Similarity).

**Character/string-level edit distances (Levenshtein, Jaro-Winkler, …) are out
of scope** — they live in the
[edit-distance-service](../edit-distance-service). This service focuses
exclusively on semantics.

**Lightweight by default.** The base install ships only `nltk` (~1.8 MB wheel +
WordNet corpus) and `scikit-learn` (~35-45 MB) — so the WordNet and TF-IDF
families work out of the box. Everything that needs a large model download
(PyTorch-based SBERT/BERTScore, gensim word vectors) is an **opt-in extra**
(`pip install -e ".[model]"`); see
[Model-based measures](#model-based-measures-optional).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/text/algorithms` | Discovery — list all algorithm/backend combinations with metadata |
| `POST` | `/v1/text/distance` | Compute text similarity (synchronous, batch) |
| `POST` | `/v1/text/retrieval` | Rank query candidates (synchronous, batch) |
| `POST` | `/v1/text/lexical` | Look up lexical relations (synchronous, batch) |

All compute endpoints are synchronous and stateless: every request takes
`algorithm` (+ optional `backend`), `params` and a batch `inputs` list, and
returns one result per input. When `backend` is omitted, the algorithm's
default backend (marked `default: true` in `/v1/text/algorithms`) is
auto-selected.

## Algorithms

- **`/v1/text/distance`** (similarity) — two texts in, one normalized semantic
  score out (`wordnet_similarity`, `embedding_cosine`, `sbert_cosine`, `wmd`,
  `cross_encoder`, `tfidf_cosine`, `bertscore`, `topic_model`,
  `structural_stylistic`). Inputs: `{"id", "a", "b"}`.
- **`/v1/text/retrieval`** (retrieval) — one query + candidates in, a ranked
  match list out (`semantic_search`). Inputs: `{"id", "query", "candidates"}`.
- **`/v1/text/lexical`** (lexical_relations) — one word in, a set of related
  words out (`synonym`, `antonym`, `hypernym`). Inputs: `{"id", "word"}`.

## Example

```sh
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "wordnet_similarity",
    "params": {"variant": "path"},
    "inputs": [
      {"id": "p1", "a": "car", "b": "automobile"}
    ]
  }' | jq .
```

```json
{
  "algorithm": "wordnet_similarity",
  "backend": "nltk",
  "results": [
    {
      "id": "p1",
      "result": {
        "raw": 1.0,
        "similarity": 1.0,
        "distance": 0.0,
        "compute_time_ms": 0.7
      }
    }
  ],
  "meta": {"compute_time_ms": 0.7}
}
```

Here `car` and `automobile` are in the same WordNet synset, so their semantic
similarity is `1.0` — while e.g. `car` vs `banana` scores only ~`0.08`.

## Model-based measures (optional)

**Design goal:** every library / algorithm that requires a model download is
**optional**. The base install and the default Docker image stay small; the
neural/embedding families are enabled explicitly.

### Why this is needed

The algorithm libraries themselves are tiny:

| Library | Size | Used by |
|---|---|---|
| `nltk` | ~1.8 MB wheel | WordNet lexical measures (+ ~12 MB WordNet corpus at runtime) |
| `scikit-learn` | ~35-45 MB | TF-IDF vector-space cosine (`tfidf_cosine`) |
| `gensim` | ~50 MB | static word embeddings (`embedding_cosine`, `wmd`) |
| `sentence-transformers` + `torch` | **~2.5 GB** | SBERT cosine / cross-encoder / semantic search |
| `bert-score` + `torch` | **~2.5 GB** | BERTScore evaluation metric |

Only the last two rows pull in **PyTorch (~2.5 GB CUDA wheel)** and download
models at runtime (HuggingFace checkpoints, gensim GloVe vectors ~200 MB).
Bundling those into every install / image would inflate it to ~5 GB for the
sake of a few neural/embedding families.

### What is optional

| Scope | Installed | Families enabled |
|---|---|---|
| **Base** (always) | `nltk`, `scikit-learn` (+ FastAPI stack) | WordNet similarity, TF-IDF, lexical relations, `semantic_search` (TF-IDF variant) — **6/13** |
| **`[model]` extra** | `sentence-transformers`, `bert-score`, `gensim` (+ PyTorch) | `embedding_cosine`, `sbert_cosine`, `wmd`, `cross_encoder`, `bertscore` — **+5/13** |
| **DKPro sidecar** | separate Java service | `topic_model`, `structural_stylistic` (routed) |

### Coverage table

| # | Family | Backend | Needs `[model]`? |
|---|---|---|---|
| 1 | WordNet path/IC similarity (`wordnet_similarity`) | nltk (default) | — (WordNet corpus) |
| 2 | Synonym lookup | nltk | — (WordNet corpus) |
| 3 | Antonym lookup | nltk | — (WordNet corpus) |
| 4 | Hypernym / Hyponym lookup | nltk | — (WordNet corpus) |
| 5 | TF-IDF vector-space cosine (`tfidf_cosine`) | scikit-learn | — |
| 6 | Semantic search (`semantic_search`) | sentence-transformers (default), gensim | ✅ only the sentence-transformers backend; the gensim variant uses TF-IDF and runs on base |
| 7 | Static word/doc embedding (`embedding_cosine`) | gensim | ✅ `[model]` (+ GloVe download) |
| 8 | Transformer sentence embedding (`sbert_cosine`) | sentence-transformers | ✅ `[model]` (PyTorch) |
| 9 | Word Mover's Distance (`wmd`) | gensim | ✅ `[model]` (+ GloVe download) |
| 10 | Contextual eval metric (`bertscore`) | bert-score | ✅ `[model]` (PyTorch) |
| 11 | Cross-encoder reranking (`cross_encoder`) | sentence-transformers | ✅ `[model]` (PyTorch) |
| 12–13 | Topic-model / Structural-stylistic | dkpro (Java sidecar) | separate optional sidecar |

### Enabling the model stack

```sh
pip install -e ".[model]"   # sentence-transformers + gensim + bert-score (+ PyTorch)
```

- Imports are **lazy** — the base service never loads PyTorch/gensim unless a
  model-based algorithm is actually called.
- The models themselves (HuggingFace SBERT/BERTScore checkpoints, gensim GloVe)
  are **downloaded on first use and cached in memory** (`src/model_cache.py`),
  not bundled into the image.
- Without the extra, model-based endpoints return a clean
  `501 problem+json` naming the missing module and the install command; all
  other measures keep working unchanged.

### Docker

The default image is the light base (`docker build -f Dockerfile -t
text-similarity-service .`, ~150 MB of deps + base image ≈ 750 MB). Build the
full model stack explicitly:

```sh
docker build --build-arg INSTALL_MODEL=true -t text-similarity-service .
```

A BuildKit pip cache (`--mount=type=cache`) reuses downloads across builds, so
rebuilding with the model stack is only expensive once.

## DKPro Sidecar (optional)

Two measures — `topic_model` and `structural_stylistic` — and the optional
`backend: "dkpro"` variants on two other tags (`tfidf_cosine`,
`wordnet_similarity`) are implemented by a separate Java service in
[`dkpro-sidecar/`](dkpro-sidecar/), called internally via HTTP.

The Python service is fully functional without the sidecar: every other measure
works, and `GET /v1/text/algorithms` still lists the DKPro entries. A request to a
DKPro-backed measure returns a clean `502/503 problem+json` when the sidecar is
not running.

The sidecar requires building DKPro Similarity from source (`git clone
https://github.com/dkpro/dkpro-similarity && mvn install`), JDK 21 + Maven, and
an extra JVM process — enable it only if those two measures are a hard
requirement.

## Development

```sh
make prep    # install dependencies
make test    # run tests
make lint    # run ruff
make start   # run uvicorn on :8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | Base URL of the DKPro Java sidecar |

## Data Dependencies

Data is never bundled into the image; it is downloaded on first use and cached
in memory (`src/model_cache.py`). Sizes and requirements:

| Data | Size | Needed by | Extra? |
|------|------|-----------|--------|
| NLTK WordNet corpus | ~12 MB download / ~35 MB unpacked | `wordnet_similarity`, `synonym`, `antonym`, `hypernym`, `hyponym` | — (small runtime download, base install) |
| NLTK Information Content corpus | small | `wordnet_similarity` variants `res`/`jcn`/`lin` | — |
| HuggingFace models (SBERT `all-MiniLM-L6-v2`, cross-encoder, BERTScore) | 100–400 MB each | `sbert_cosine`, `cross_encoder`, `bertscore`, SBERT backend of `semantic_search` | ✅ `[model]` |
| gensim GloVe vectors (`glove-wiki-gigaword-50`) | ~200 MB | `embedding_cosine`, `wmd` | ✅ `[model]` |

Run `nltk.download('wordnet')` once for the lexical measures. The HuggingFace
and gensim models are fetched automatically on first use when the `[model]`
extra is installed.

## License

MIT
