# Text Similarity Service

Semantic text similarity service — measures the *meaning* similarity of words, sentences, and documents, and looks up lexical relations (synonym/antonym/hypernym/hyponym).

> **Character/string edit distances are out of scope** — those live in [edit-distance-service](../edit-distance-service).

---

## Quick orientation

Before using this service, understand **three independent decisions**. Everything else is per-algorithm detail you can look up at runtime via `GET /v1/similarity/text/algorithms`.

**1. Which image?** Two images differ *only* in the PyTorch/HuggingFace models.

| Image | Enables |
|---|---|
| `text-similarity-cpu` (default, ~730 MB) | Base algorithms — no PyTorch |
| `text-similarity-pytorch` | Base **+** SBERT/BERTScore/cross-encoder/semantic_search |

**2. Is the optional Java DKPro sidecar running?** If yes, you also get `topic_model`, `structural_stylistic`, and `dkpro` backends for two base algorithms. If no, those requests fail with `502/503`.

**3. Do you allow the external ConceptNet API?** Only one algorithm variant (`embedding_cosine` / `conceptnet_numberbatch` / `backend: remote`) calls a third-party API — and only when you ask for it explicitly. Its alternative is a local ~1.2 GB model download. Everything else is fully self-contained. See [External API](#external-api).


---

## Full algorithm reference

> Source of truth: the live catalog at `GET /v1/similarity/text/algorithms`. Not all of the below is enabled in every build — see the "runs in" column.

| Endpoint | Algorithm | Backend | Runs in | Variants / notes |
|---|---|---|---|---|
| `/distance` | `wordnet_similarity` | `nltk`, `dkpro`\* | **cpu** + pytorch | `path` (default), `wup`, `lch`, `res`, `jcn`, `lin` |
| `/distance` | `tfidf_cosine` | `sklearn`, `dkpro`\* | **cpu** + pytorch | vector-space cosine |
| `/distance` | `token_set_overlap` | `builtin` | **cpu** + pytorch | `jaccard` (default) / `dice` |
| `/distance` | `jaccard` / `dice` | `builtin` | **cpu** + pytorch | legacy aliases of `token_set_overlap` |
| `/distance` | `embedding_cosine` | `gensim` | **cpu** + pytorch | `glove` (default), `fasttext`†, `conceptnet_numberbatch` (remote default / local†) |
| `/distance` | `wmd` | `gensim` | **cpu** + pytorch | Word Mover's Distance; `params.model_name` |
| `/distance` | `sbert_cosine` | `sentence_transformers` | **pytorch only** | `params.model_name` restricted to allow-list |
| `/distance` | `cross_encoder` | `sentence_transformers` | **pytorch only** | pairwise reranking |
| `/distance` | `bertscore` | `bertscore` | **pytorch only** | P/R/F1; `lang`-based default = `roberta-large` |
| `/distance` | `topic_model` | `dkpro`\* | **sidecar required** | LSA / ESA |
| `/distance` | `structural_stylistic` | `dkpro`\* | **sidecar required** | n-gram containment / TTR / greedy string tiling |
| `/retrieval` | `bm25` | `builtin` | **cpu** + pytorch | `k1` (1.5), `b` (0.75), `top_k` (10) |
| `/retrieval` | `semantic_search` | `sentence_transformers` | **pytorch only** | nearest-neighbor retrieval |
| `/lexical` | `synonym` / `antonym` / `hypernym` / `hyponym` | `nltk`, `odenet` | **cpu** + pytorch | `odenet` = German (needs `[de]` extra) |

\* `dkpro` backend requires the Java sidecar — works with **either** image.
† Large download — gated (see [Resource gate](#resource-gate-for-large-downloads)).

### Notable algorithms

- **BM25** — pure-stdlib lexical retrieval; the only base-tier, non-model retrieval algorithm.
- **Odenet** — `synonym`/`antonym`/`hypernym`/`hyponym` with `backend: "odenet"` serve *German* via Open German WordNet (requires `[de]` extra, auto-downloads on first use).
- **HuggingFace allow-list** — `sbert_cosine`, `semantic_search`, `cross_encoder`, `bertscore` only accept a short curated model list (`src/model_cache.py::_ALLOWED_BASE_MODELS`); anything else is rejected with `400`.

---

## External API

`embedding_cosine` variant `conceptnet_numberbatch`, `backend: "remote"` (the default for that variant) calls the public ConceptNet API — **not under our control**:

- `GET https://api.conceptnet.io/relatedness?node1=/c/{lang}/{a}&node2=/c/{lang}/{b}`
- no auth · rate limit 3600 req/h sustained, 120 req/min burst

It's **selected per request**, not a global switch:

| Want external API? | Request |
|---|---|
| **Off** (default) | use `glove`/`fasttext` variant, or any other algorithm |
| **On** | `params: {variant: conceptnet_numberbatch, backend: remote}` |
| **On, fully offline** | `params: {variant: conceptnet_numberbatch, backend: local}` → local ~1.2 GB download (gated) |

Safeguards: ~5 s timeout, batch cap `CONCEPTNET_MAX_REMOTE_INPUTS` (60), throttle `CONCEPTNET_REMOTE_REQUEST_DELAY` (0.05 s), 429 backoff retries. Failures → `503` (timeout/network/429) or `502` (other upstream) — **never** silent fallback to the 1.2 GB download. `glove`/`fasttext` have no remote backend (no public API exists); `backend: remote` on them is rejected with `400`.

---

## Resource requirements

### Base (CPU-only)
**RAM < 1 GB · CPU 1–2 cores · machine downloads ~12–200 MB.** Runs on any small host; no GPU.

### PyTorch / HuggingFace
| Measure | Model (default) | Download | RAM to run | CPU vs GPU |
|---|---|---|---|---|
| `sbert_cosine`, `semantic_search` | `all-MiniLM-L6-v2` | ~90 MB | ~0.5–1 GB | CPU fine; small & fast |
| `sbert_cosine` (heavier) | `all-mpnet-base-v2` | ~420 MB | ~2–4 GB | CPU usable; GPU recommended at volume |
| `cross_encoder` | `stsb-roberta-base` | ~440 MB | ~2–4 GB | GPU recommended for real-time |
| `bertscore` | `roberta-large` | several 100 MB | ~2–4 GB+ | **GPU strongly recommended** |
| `embedding_cosine` (`fasttext`) | `fasttext-wiki-news-subwords-300` | ~2 GB | ~4–8 GB | CPU only |
| `embedding_cosine` (`conceptnet` local) | `conceptnet-numberbatch-17-06-300` | ~1.2 GB | ~3–6 GB | CPU only |

- No measure *requires* a GPU; GPU only cuts transformer latency.
- In-memory footprint ≈ **4× the download size** (float32 + runtime libs).
- Heavy models are **cached per process** (`src/model_cache.py`); more workers = more RAM.

### DKPro sidecar
Extra Java process: ~2 cores, 1–2 GB RAM alongside the Python service.

---

## Resource gate

Any runtime download **> 500 MB** needs `params.confirm_large_download: true`, or the env `ALLOW_LARGE_MODEL_DOWNLOADS=true`. HuggingFace checkpoints are also allow-list-restricted. Smaller corpora (WordNet ~12 MB, Odenet ~10–30 MB, GloVe ~200 MB) download automatically.

---

## API

Synchronous & stateless: `{"algorithm", "params", "inputs":[...]}` → result per input. Omitted `backend` selects the default (marked `default: true` in `/v1/similarity/text/algorithms`).

| Method | Path | Description |
|---|---|---|
| `GET` | `/health`, `/health/ready` | Liveness / readiness |
| `GET` | `/v1/similarity/text/algorithms` | Discovery — every algorithm/backend combo |
| `POST` | `/v1/similarity/text/distance` | Similarity score for two texts |
| `POST` | `/v1/similarity/text/retrieval` | Rank query candidates |
| `POST` | `/v1/similarity/text/lexical` | Lexical relations for a word |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SIMILARITY_PROFILE` | `cpu` | image/run profile (`cpu` / `pytorch`), baked in at build |
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | DKPro Java sidecar URL |
| `CONCEPTNET_API_URL` | `https://api.conceptnet.io` | ConceptNet relatedness API base |
| `CONCEPTNET_MAX_REMOTE_INPUTS` | `60` | max inputs/request for `remote` backend |
| `CONCEPTNET_REMOTE_REQUEST_DELAY` | `0.05` | min seconds between API calls |
| `CONCEPTNET_429_RETRIES` | `3` | max backoff retries on HTTP 429 |
| `ALLOW_LARGE_MODEL_DOWNLOADS` | `false` | server-wide opt-in for downloads > 500 MB |

## Development

```sh
make prep                    # base deps (cpu profile)
pip install -e ".[model]"    # + PyTorch / HuggingFace
pip install -e ".[de]"       # + German lexical (Odenet)
make docker-build-cpu        # text-similarity-cpu
make docker-build-pytorch    # text-similarity-pytorch
make test                    # run tests
make start                   # uvicorn on :8000
```

## License

MIT
