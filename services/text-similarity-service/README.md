# text-similarity-service

Unified REST API for text similarity — 23 algorithm families over 8 backends
(NLTK, RapidFuzz, sentence-transformers, gensim, scikit-learn, textdistance,
BERTScore, DKPro Similarity).

## Overview

This service exposes a single 4-endpoint contract (`GET /v1/measures`,
`POST /v1/compute`, `GET/DELETE /v1/results/{id}`) over a discriminated union of
23 text-similarity algorithm families (Spec C / full coverage).

Families 1–21 run in-process (Python). Families 22–23 (`topic_model`,
`structural_stylistic`) and the optional DKPro backends are handled by a Java
sidecar located in [`dkpro-sidecar/`](dkpro-sidecar/), which is called
internally via HTTP when `backend: "dkpro"` is requested.

## DKPro Sidecar (Optional)

> ⚠️ **The DKPro sidecar is optional.** The Python service is fully functional
> without it (21/23 families, 91% coverage). Enable it only if families 22–23
> are a hard requirement.

**What you get (the 9%):**

| Family | Tag | Description |
|---|---|---|
| 22 | `topic_model` | Topic-model similarity (LSA / ESA) |
| 23 | `structural_stylistic` | Structural/stylistic similarity (n-gram containment, type-token ratio, greedy string tiling) |

Plus 5 optional DKPro backend variants on already-covered tags (`token_set`,
`lcs`, `phonetic`, `tfidf_cosine`, `wordnet_similarity`) — these add **no**
new family coverage, only alternative implementations.

**What it costs:**

- DKPro Similarity is **Java + Apache UIMA**: not published on Maven Central,
  must be built from source (`git clone https://github.com/dkpro/dkpro-similarity
  && mvn install`)
- Requires JDK 21 + Maven + the UIMA runtime; roughly **8 years stale** upstream
- Runs as a **separate process** (the sidecar), increasing deployment and
  operational complexity (memory, JVM, separate container)
- Requests to `topic_model`/`structural_stylistic` fail with a clean 502/503
  problem+json if the sidecar is not running

**How to skip it:** leave `TEXT_SIMILARITY_DKPRO_URL` unset or don't deploy the
sidecar — every other measure works normally, and `GET /v1/measures` still lists
the DKPro entries so clients can discover them (calls will fail if the sidecar
is absent). The CI workflow only builds the sidecar when `dkpro-sidecar/**`
changes, and no Python job depends on it.

## Development

```sh
make prep    # install dependencies
make test    # run tests
make lint    # run ruff
make start   # run uvicorn on :8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok", "service": "text-similarity-service"}` |
| `GET` | `/v1/measures` | Discovery — list all 23 operation/measure/backend combinations with metadata |
| `POST` | `/v1/compute` | Run a computation — accepts a discriminated-union body (operation → measure → backend → params). Returns `201 Created` (sync) or `202 Accepted` (async) with a Result resource envelope |
| `GET` | `/v1/results/{id}` | Retrieve a previously computed result |
| `DELETE` | `/v1/results/{id}` | Release a stored result resource |

### Operations

- **`similarity`** — two inputs in, one normalized score out (Levenshtein … BERTScore)
- **`retrieval`** — one query + many candidates in, a ranked list out (fuzzy extract, semantic search)
- **`lexical_relations`** — one word in, a set of related words/synsets out (synonym, antonym, hypernym)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | Base URL of the DKPro Java sidecar for `topic_model`, `structural_stylistic`, and optional `backend: "dkpro"` requests |

## Data Dependencies

- NLTK WordNet corpus (`nltk.download('wordnet')`) — required for
  `wordnet_similarity`, `synonym`, `antonym`, `hypernym`, `hyponym`
- NLTK Information Content corpus — required for `wordnet_similarity`
  variants `res`/`jcn`/`lin` (documented in the API spec §7)

## License

MIT