# Text Similarity Service

Semantic text similarity service — measures the *meaning* similarity of words, sentences, and documents, and looks up lexical relations (synonym/antonym/hypernym/hyponym).

> **Character/string edit distances are out of scope** — those live in [edit-distance-service](../edit-distance-service).

---

## Quick orientation

Before using this service, understand **three independent decisions**. Everything else is per-algorithm detail you can look up at runtime via `GET /v1/similarity/text/algorithms`.

**1. Which image?** Two images differ in the PyTorch/HuggingFace models they ship. The local ConceptNet Numberbatch model no longer lives in any main image — it runs as an optional sidecar (see [ConceptNet sidecar](#conceptnet-sidecar)).

| Image | Enables |
|---|---|
| `text-similarity-cpu` (default, ~0.7–1 GB) | Base algorithms — no PyTorch |
| `text-similarity-hf` | Base **+** SBERT/BERTScore/cross-encoder/semantic_search — the lightest full-stack image |

- `text-similarity-cpu` offers no PyTorch models at all; a request for one is rejected with a 400 pointing at the `hf` image. This is the default build (smallest, no heavy downloads).
- `text-similarity-hf` is the recommended light "everything-else" deployment: built with [`HF_PRELOAD=all`](#hf_preload-build-arg) it pre-caches all HuggingFace models (`all-MiniLM-L6-v2`, `all-mpnet-base-v2`, `paraphrase-multilingual-MiniLM-L12-v2`, `stsb-roberta-base`, `roberta-large`) to disk at build time (and warms them into RAM at start), so SBERT/cross-encoder/BERTScore serve instantly from a fresh container — offline. It is the **only** full-feature build; ConceptNet Numberbatch is served by the optional sidecar, never pre-cached into the image.
- `embedding_cosine` / `conceptnet_numberbatch` with `params.backend=local` is served by the ConceptNet sidecar; with no sidecar configured it returns `502/503` (see below), never a local in-process computation or download.

**2. Is the optional ConceptNet sidecar running?** If yes, `embedding_cosine` / `conceptnet_numberbatch` / `params.backend: local` is served by the separate `conceptnet-sidecar` process. If no, those requests fail with `502/503`. See [ConceptNet sidecar](#conceptnet-sidecar).

**3. Do you allow the external ConceptNet API?** Only one algorithm variant (`embedding_cosine` / `conceptnet_numberbatch` / `backend: remote`) calls a third-party API — and only when you ask for it explicitly. Everything else is fully self-contained. See [External API](#external-api).


---

## Full algorithm reference

> Source of truth: the live catalog at `GET /v1/similarity/text/algorithms`. Not all of the below is enabled in every build — see the "runs in" column.

| Endpoint | Algorithm | Backend | Runs in | Variants / notes |
|---|---|---|---|---|
| `/distance` | `wordnet_similarity` | `nltk` | **cpu** + pytorch | `path` (default), `wup`, `lch`, `res`, `jcn`, `lin` — IC variants load the corpus server-side |
| `/distance` | `tfidf_cosine` | `sklearn` | **cpu** + pytorch | vector-space cosine |
| `/distance` | `token_set_overlap` | `builtin` | **cpu** + pytorch | `jaccard` (default) / `dice` |
| `/distance` | `jaccard` / `dice` | `builtin` | **cpu** + pytorch | legacy aliases of `token_set_overlap` |
| `/distance` | `embedding_cosine` | `gensim` | **cpu** + pytorch | `glove` (default), `fasttext`†, `conceptnet_numberbatch` (sidecar default / remote opt-in) |
| `/distance` | `wmd` | `gensim` | **cpu** + pytorch | Word Mover's Distance; `params.model_name` |
| `/distance` | `sbert_cosine` | `sentence_transformers` | **hf** | `params.model_name` restricted to allow-list |
| `/distance` | `cross_encoder` | `sentence_transformers` | **hf** | pairwise reranking |
| `/distance` | `bertscore` | `bertscore` | **hf** | P/R/F1; `lang`-based default = `roberta-large` |
| `/distance` | `topic_model` | `builtin` | **cpu** + pytorch | corpus-free LSI (`lsa`/`esa` aliases) |
| `/distance` | `structural_stylistic` | `builtin` | **cpu** + pytorch | n-gram containment / type-token ratio / greedy string tiling |
| `/retrieval` | `bm25` | `builtin` | **cpu** + pytorch | `k1` (1.5), `b` (0.75), `top_k` (10) |
| `/retrieval` | `semantic_search` | `sentence_transformers` | **hf** | nearest-neighbor retrieval |
| `/lexical` | `synonym` / `antonym` / `hypernym` / `hyponym` | `nltk`, `odenet` | **cpu** + pytorch | `odenet` = German (needs `[de]` extra) |

† Large download — gated (see [Resource gate](#resource-gate-for-large-downloads)).

### Notable algorithms

- **BM25** — pure-stdlib lexical retrieval; the only base-tier, non-model retrieval algorithm.
- **Odenet** — `synonym`/`antonym`/`hypernym`/`hyponym` with `backend: "odenet"` serve *German* via Open German WordNet (requires `[de]` extra, auto-downloads on first use).
- **HuggingFace allow-list** — `sbert_cosine`, `semantic_search`, `cross_encoder`, `bertscore` only accept a short curated model list (`src/model_cache.py::_ALLOWED_BASE_MODELS`); anything else is rejected with `400`.

---

## External API

`embedding_cosine` variant `conceptnet_numberbatch` is served locally by the optional ConceptNet sidecar; `backend: "remote"` (an **explicit opt-in**; the default is to the local sidecar/service path) calls the public ConceptNet API — **not under our control**:

- `GET https://api.conceptnet.io/relatedness?node1=/c/{lang}/{a}&node2=/c/{lang}/{b}`
- no auth · rate limit 3600 req/h sustained, 120 req/min burst

It's **selected per request**, not a global switch:

| Want external API? | Request |
|---|---|
| **Off** (default) | `params: {variant: conceptnet_numberbatch}` → local path via the ConceptNet sidecar |
| **On** | `params: {variant: conceptnet_numberbatch, backend: remote}` |
| **On, fully offline** | `params: {variant: conceptnet_numberbatch, backend: local}` → same as the default, explicit |

Safeguards: ~5 s timeout, batch cap `CONCEPTNET_MAX_REMOTE_INPUTS` (60), throttle `CONCEPTNET_REMOTE_REQUEST_DELAY` (0.05 s), 429 backoff retries. Failures → `503` (timeout/network/429) or `502` (other upstream). The remote path only runs when explicitly requested (`backend: remote`) and never silently downgrades to any other backend. `glove`/`fasttext` have no remote backend (no public API exists); `backend: remote` on them is rejected with `400`.

## ConceptNet sidecar

> **Is the optional ConceptNet sidecar running?** If yes, `embedding_cosine` /
> `conceptnet_numberbatch` / `params.backend: local` is served by the separate
> `conceptnet-sidecar` process (pure Python + gensim) instead of a model loaded
> in-process. If no, those requests fail with `502/503` — the main service process
> stays healthy, it never crashes and never falls back to a local download.

The sidecar lives in `conceptnet-sidecar/` (see its [README](conceptnet-sidecar/README.md)),
with its URL configured via `TEXT_SIMILARITY_CONCEPTNET_URL` (default
`http://localhost:8200`). It works with **either** main image (`cpu`/`hf`). Run it locally with:

```sh
cd conceptnet-sidecar
make prep
CONCEPTNET_MODEL_PATH=/path/to/conceptnet-numberbatch-17-06-300 make test
CONCEPTNET_MODEL_PATH=/path/to/conceptnet-numberbatch-17-06-300 make start   # uvicorn on :8200
```

**Lazy-load + TTL.** The sidecar does **not** load the ~1.2 GB model at startup. It
loads on the first `/v1/relatedness` request, and evicts the model from RAM after
`CONCEPTNET_IDLE_TTL_SECONDS` (default 900 s) of inactivity — so an idle sidecar sits
at < 200 MB, not ~3-6 GB (see [ADR-0001](docs/adr/0001-conceptnet-as-sidecar.md) and
[Resource requirements](#resource-requirements)). A request immediately after an
eviction re-loads the model automatically; that one call just takes longer.

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

- No measure *requires* a GPU; GPU only cuts transformer latency.
- In-memory footprint ≈ **4× the download size** (float32 + runtime libs).
- Heavy models are **cached per process** (`src/model_cache.py`); more workers = more RAM.
- **Warm start (`HF_PRELOAD=all`):** cold by default (boot ~1 s, idle RAM ~0.05 GB, but the *first* model request pays the transformer load, ~6–21 s). `HF_PRELOAD=all` pre-downloads every advertised HF model onto the image disk at build time **and** loads them into RAM at startup, so the first request returns in milliseconds — in exchange for a longer boot (~1–2 min) and higher idle RAM that **scales with the selected models** (each transformer adds roughly its "RAM to run" value below — a single MiniLM ~0.5–1 GB; all advertised models sum to ~7–10+ GB). A partial `HF_PRELOAD=measure:model,...` list warms only those (and pre-downloads only those to disk). This is the main service's analogue of the ConceptNet sidecar's `CONCEPTNET_PRELOAD_ON_START`. Warm loads are non-fatal (a failure relaxes to lazy loading). See [`/metrics`](#api) (`"warm"` + `model_cache.keys`).

### ConceptNet sidecar

Runs in its own process (`conceptnet-sidecar`), so its RAM is isolated from the main
service (see [ADR-0001](docs/adr/0001-conceptnet-as-sidecar.md)). It loads the
~1.2 GB Numberbatch model **lazily** on first request and evicts it from RAM after an
inactivity TTL:

| State | RAM |
|---|---|
| Active (model loaded) | ~3–6 GB (CPU only) |
| Idle (`CONCEPTNET_IDLE_TTL_SECONDS` elapsed, model evicted) | **< 200 MB** |

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
| `TEXT_SIMILARITY_CONCEPTNET_URL` | `http://localhost:8200` | ConceptNet sidecar URL for `embedding_cosine` / `conceptnet_numberbatch` / `params.backend: local` |
| `CONCEPTNET_API_URL` | `https://api.conceptnet.io` | ConceptNet relatedness API base |
| `CONCEPTNET_MAX_REMOTE_INPUTS` | `60` | max inputs/request for `remote` backend |
| `CONCEPTNET_REMOTE_REQUEST_DELAY` | `0.05` | min seconds between API calls |
| `CONCEPTNET_429_RETRIES` | `3` | max backoff retries on HTTP 429 |
| `ALLOW_LARGE_MODEL_DOWNLOADS` | `false` | server-wide opt-in for downloads > 500 MB |
| `HF_PRELOAD` | `off` | preload profile for HF models, **baked in at build** (see [`HF_PRELOAD` build-arg](#hf_preload-build-arg)): `off` = cold (nothing on disk, all lazy), `all` = warm (every HF model pre-downloaded to disk + loaded into RAM), or partial `measure:model[,measure:model...]` |

## Development

```sh
make prep                    # base deps (cpu profile)
pip install -e ".[model]"    # + PyTorch / HuggingFace
pip install -e ".[de]"       # + German lexical (Odenet)
make docker-build-cpu        # text-similarity-cpu (no PyTorch; HF_PRELOAD=off)
make docker-build-hf         # text-similarity-hf, HF_PRELOAD=off (cold start)
make docker-build-hf HF_PRELOAD=all   # mode 2: disk + RAM warmed, 1st request in ms
make docker-build-hf HF_PRELOAD="sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large"  # partial
make test                    # run tests
make start                   # uvicorn on :8000

# ConceptNet sidecar (optional, separate process — see conceptnet-sidecar/)
cd conceptnet-sidecar
make prep
CONCEPTNET_MODEL_PATH=/path/to/conceptnet-numberbatch-17-06-300 make docker-build
```

- **`text-similarity-hf`** built with `HF_PRELOAD=all` pre-downloads all five HuggingFace models to the image disk at build time (and warms them into RAM at start) so the first SBERT/cross-encoder/BERTScore request is served offline from a fresh container. Image size ≈ base + PyTorch/CUDA (~5.5 GB) + HF models (~2.9 GB). With `HF_PRELOAD=off` (default) the same image skips the pre-download entirely (smaller build, cold start, lazy runtime download).
- The local ConceptNet Numberbatch model is **no longer baked into any main image** — it lives in the `conceptnet-sidecar` container and is loaded lazily there (see [ConceptNet sidecar](#conceptnet-sidecar)).
- The default `text-similarity-cpu` stays small (~0.7–1 GB) and downloads the small corpora (WordNet, GloVe) at runtime.
- For manual control, bypass the `make` targets and pass build args directly:
  `docker build --build-arg SIMILARITY_PROFILE=pytorch --build-arg INSTALL_MODEL=true \
   --build-arg HF_PRELOAD=all -t text-similarity-hf .`

### `HF_PRELOAD` build-arg

`HF_PRELOAD` is the **one switch** that controls both sides of the HF models:
which weights are **pre-downloaded onto the image disk** (build time) and which
are **loaded into RAM** (container start). It is **baked in at build time**
(pushed into the image as `ENV HF_PRELOAD`), so a given image self-describes its
preload behaviour — no runtime config needed. The same selection drives the
disk pre-cache (`src/__precache_hf.py`) and the RAM warm-start (`warm_start`),
so what runs warm can never drift from what is on disk.

**Mode 1 — cold (`HF_PRELOAD=off`, default):** nothing is pre-downloaded and
nothing is warmed. Every model is lazy-loaded (downloading if absent) on its
first request.
**Mode 2 — warm (`HF_PRELOAD=all`):** every advertised model pre-downloaded to
disk **and** loaded into RAM at startup. First request served instantly, offline.
**Partial (`HF_PRELOAD=measure:model,...`):** only the selected models are
pre-downloaded and warmed; everything else is absent (lazy runtime download).

| `HF_PRELOAD` | Mode | Disk (build) | RAM (start) | Boot | Idle RAM |
|---|---|---|---|---|---|
| `off` (default) | **1 – cold** | empty | none; all lazy | ~1 s | ~0.05 GB |
| `all` | **2 – warm** | all advertised | all advertised | ~1–2 min | ~7–10+ GB (sum of model RAM) |
| `measure:model[,measure:model...]` | partial | only those | only those | between, by how many models | scales with those models |

Partial example — warm only the lightweight MiniLM and BERTScore, keep MPNet,
cross-encoder, and multilingual absent (lazy):

```sh
docker build -f Dockerfile \
  --build-arg SIMILARITY_PROFILE=pytorch --build-arg INSTALL_MODEL=true \
  --build-arg HF_PRELOAD="sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large" \
  -t text-similarity-hf .
```

Selectable measures: `sbert_cosine`, `semantic_search`, `cross_encoder`,
`bertscore`; model names must be on the algorithm allow-list and large
downloads gated as described in [Resource gate](#resource-gate)
(unknown measures/models are logged and skipped, never fatal). The current
configured profile shows under `/metrics` as `"warm"` and the actually-resident
models under `model_cache.keys`. See [Resource requirements](#resource-requirements).

The `conceptnet_numberbatch` variant's behavior no longer depends on the build: both
images serve it through the optional ConceptNet sidecar (or return `502/503` when the
sidecar is down). The legacy `SIMILARITY_DISABLE_LOCAL_CONCEPTNET` switch no longer
exists — there is no in-process Numberbatch model to hide.


## License

MIT
