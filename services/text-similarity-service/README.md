# text-similarity-service

**Semantic text similarity service** — measures how *similar the meaning* of
words, sentences and documents is, and looks up lexical relations
(synonym/antonym/hypernym/hyponym). 16 algorithm families over multiple
backends (NLTK, Odenet, sentence-transformers, gensim, scikit-learn, BERTScore,
DKPro Similarity, plus pure-Python measures).

**Character/string-level edit distances (Levenshtein, Jaro-Winkler, …) are out
of scope** — they live in the
[edit-distance-service](../edit-distance-service):

```text
text-distance-service   = character/string-level distances
text-similarity-service = semantic/lexical/statistical similarity
```

Three independent things matter for how expensive the service is to run:

1. **Build variant** — one repo builds **two images** that differ only in the
   PyTorch stack: `text-similarity-cpu` (base, no PyTorch) and
   `text-similarity-pytorch` (full). Tag separates them; each has its own
   OpenAPI spec. See [Build variants](#build-variants).

2. **Resource gate** — large *runtime* model downloads (> 500 MB) can't be
   triggered by accident; they need an explicit opt-in. "Cost" here means
   **disk/RAM/CPU resource usage on the server that hosts this service** —
   not a monetary or paid-tier cost. Nothing in this service requires
   payment; see
   [Resource gate for large downloads](#resource-gate-for-large-downloads).
3. **Host compute** — the optional model-backed measures don't just *download*
   weights; at request time they also need **RAM to hold the loaded model** and
   **CPU time (or a GPU) to run inference** on every request. The download size
   alone understates what a measure needs at runtime. Concrete per-model
   numbers (download, RAM to run, CPU vs. GPU) are in
   [Runtime resource requirements](#runtime-resource-requirements-cpu-ram-gpu).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/similarity/text/algorithms` | Discovery — list all algorithm/backend combinations with metadata |
| `POST` | `/v1/similarity/text/distance` | Compute text similarity (synchronous, batch) |
| `POST` | `/v1/similarity/text/retrieval` | Rank query candidates (synchronous, batch) |
| `POST` | `/v1/similarity/text/lexical` | Look up lexical relations (synchronous, batch) |

## Build variants (1 repo → 2 images)

One Dockerfile builds two images that differ **only** in the PyTorch stack
(`sentence-transformers`, `bert-score`). The **cpu image is the default build**;
you pick the variant by tag:

| Image tag | Profile | Includes | OpenAPI spec |
|---|---|---|---|
| `text-similarity-cpu` (default) | `cpu` | everything **except** the PyTorch algorithms | `text-similarity-service-cpu.openapi.json` |
| `text-similarity-pytorch` | `pytorch` | every algorithm, incl. `sbert_cosine`, `cross_encoder`, `bertscore`, `semantic_search` | `text-similarity-service-pytorch.openapi.json` |

The variant is selected at build time via `SIMILARITY_PROFILE` (baked in as an
ENV): `cpu` (default) or `pytorch`. In the `cpu` image the PyTorch algorithms
are absent from discovery (`/v1/similarity/text/algorithms`) and a request for
one is rejected up-front with `400`, pointing at the `pytorch` image — rather
than a lazy "install the optional extra", since that extra is deliberately not
shipped in this variant.

```sh
make docker-build-cpu      # text-similarity-cpu   (base, no PyTorch)
make docker-build-pytorch  # text-similarity-pytorch (full stack)

make generate-openapi      # writes both OpenAPI specs
```

Everything else — `[de]` (Odenet), the DKPro sidecar, the large-download
resource gate — is orthogonal: available in **both** variants. Only the
PyTorch-based algorithms split the two images.

Every compute endpoint is synchronous and stateless: `algorithm` (+ optional
`backend`), `params`, and a batch `inputs` list in, one result per input out.
Omitted `backend` uses the algorithm's default (marked `default: true` in
`/v1/similarity/text/algorithms`).

## Algorithms

- **`/v1/similarity/text/distance`** — two texts in, one normalized score out:
  `wordnet_similarity`, `embedding_cosine`, `sbert_cosine`, `wmd`,
  `cross_encoder`, `tfidf_cosine`, `token_set_overlap` (variants `jaccard`/`dice`),
  `bertscore`, `topic_model`, `structural_stylistic`.
  Inputs: `{"id", "a", "b"}`.
- **`/v1/similarity/text/retrieval`** — query + candidates in, ranked matches out:
  `semantic_search` (`[model]`), `bm25` (base).
  Inputs: `{"id", "query", "candidates"}`.
- **`/v1/similarity/text/lexical`** — one word in, related words out:
  `synonym`, `antonym`, `hypernym`, `hyponym`.
  Inputs: `{"id", "word"}`.

  > `hypernym` and `hyponym` query the same WordNet/Odenet IS-A relation in
  > opposite directions (`dog` → `animal` vs. `dog` → `poodle`). Kept as
  > separate, self-documenting algorithm names — not merged.

## Example

```sh
curl -s -X POST http://localhost:8000/v1/similarity/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "wordnet_similarity",
    "params": {"variant": "path"},
    "inputs": [{"id": "p1", "a": "car", "b": "automobile"}]
  }' | jq .
```

```json
{
  "algorithm": "wordnet_similarity",
  "backend": "nltk",
  "results": [
    {"id": "p1", "result": {"raw": 1.0, "similarity": 1.0, "distance": 0.0, "compute_time_ms": 0.7}}
  ],
  "meta": {"compute_time_ms": 0.7}
}
```

`car` and `automobile` share a WordNet synset (similarity `1.0`); `car` vs.
`banana` scores ~`0.08`.

## Installation tiers

Tier is decided purely by **wheel size** — whether a dependency pulls in
PyTorch (~2.5 GB) — not by how much *data* it downloads at runtime (see
[Resource gate](#resource-gate-for-large-downloads) for that).

| Tier | Packages | Install | Families enabled |
|---|---|---|---|
| **Base** (always) | `nltk`, `scikit-learn`, `gensim` (+ FastAPI) | — | WordNet, TF-IDF, lexical relations, `token_set_overlap`, `bm25`, `embedding_cosine`, `wmd` — **10/16** |
| **`[model]`** | `sentence-transformers`, `bert-score` (+ PyTorch) | `pip install -e ".[model]"` | `sbert_cosine`, `cross_encoder`, `bertscore`, `semantic_search` — **4/16** |
| **`[de]`** | `wn` (pure Python) | `pip install -e ".[de]"` | German lexical relations via Odenet |
| **DKPro sidecar** | separate Java service | see [DKPro](#dkpro-sidecar-optional) | `topic_model`, `structural_stylistic` — **2/16** |

Imports are lazy — nothing loads until the matching algorithm is called.
Without `[model]`, its endpoints return `501 problem+json` naming the install
command; same for `[de]`. **In the `text-similarity-cpu` image the profile
switch is stricter than a 501**: the PyTorch algorithms are not advertised and
a request for one returns `400` pointing at the `pytorch` image (see
[Build variants](#build-variants-1-repo-%E2%86%92-2-images)).
`embedding_cosine`/`wmd` need no extra (`gensim` is base) — their large
downloads go through the resource gate instead (`400`, not `501`).

```sh
pip install -e ".[model]"   # SBERT / BERTScore / semantic_search
pip install -e ".[de]"      # German lexical relations (Odenet)
python -m wn download odenet:1.4   # optional — auto-downloads on first use otherwise
```

Base image: `make docker-build-cpu` → `text-similarity-cpu` ≈ 730 MB (base deps
incl. `gensim` + POT, no PyTorch). Full stack: `make docker-build-pytorch` →
`text-similarity-pytorch`. A BuildKit pip cache (`--mount=type=cache`) makes
rebuilds with the model stack cheap after the first time. Runtime model/data
downloads are **never** baked into the image, in either build: both images run
as the unprivileged `nobody` user with a writable `.cache`-style dir
(`/var/text-similarity-cache`) so HuggingFace, gensim, NLTK and Odenet data
download on first use.

## Resource gate for large downloads

> **"Cost" = server resource usage (disk space to cache the model, RAM to
> load it, CPU time to run it) — not money.** This service has no billing,
> no paid tier, and no external cost anywhere. The gate below exists purely
> so a request can't silently make the host machine download and cache a
> multi-gigabyte file / hold it in memory without the operator's consent.

The lightest path that still gives coverage runs automatically; anything with
a runtime download over the **500 MB threshold** requires an explicit opt-in
so it can never trigger by accident.

| Data | Size | Trigger | Gate |
|---|---|---|---|
| NLTK WordNet corpus | ~12 MB | `wordnet_similarity`, `synonym`, `antonym`, `hyper/hyponym` | none — automatic |
| NLTK Information Content corpus | small | `wordnet_similarity` (`res`/`jcn`/`lin`) | none — automatic |
| Odenet data | ~10–30 MB | `backend: odenet` | none — automatic (after `[de]` install) |
| gensim GloVe (`glove-wiki-gigaword-50`) | ~200 MB | `embedding_cosine` variant `glove` (default), `wmd` | none — automatic |
| ConceptNet API (remote) | 0 MB local, network call only | `embedding_cosine` variant `conceptnet_numberbatch`, `backend: remote` (default) | none — external API, see [below](#conceptnet-numberbatch-local-vs-remote) |
| HuggingFace checkpoints | 100–400 MB each | `sbert_cosine`, `cross_encoder`, `bertscore`, `semantic_search` | none — automatic (after `[model]` install) |
| gensim FastText | ~2 GB | `embedding_cosine` variant `fasttext` | **required** |
| gensim ConceptNet Numberbatch (local) | ~1.2 GB | `embedding_cosine` variant `conceptnet_numberbatch`, `backend: local` | **required** |

**Gate mechanism:** before the *first* download of a gated model, the request
needs `params.confirm_large_download: true`, or the server needs
`ALLOW_LARGE_MODEL_DOWNLOADS=true` (default `false`). Without either, the
request fails fast with `400 problem+json` naming the exact size and how to
unlock it — no silent multi-GB disk/RAM usage on the host. Already-cached
models skip the gate on later calls (the resource is already paid — in disk
space, not money — so there's nothing left to guard). Threshold and per-model
sizes live in `src/model_cache.py` (`LARGE_DOWNLOAD_THRESHOLD_MB`).

> Note: the gate guards disk usage only. RAM/CPU/GPU needed to *run* a measure are a separate, additive cost — see
> [Runtime resource requirements](#runtime-resource-requirements-cpu-ram-gpu).

```sh
# blocked
curl -s -X POST http://localhost:8000/v1/similarity/text/distance \
  -d '{"algorithm": "embedding_cosine", "params": {"variant": "fasttext"},
       "inputs": [{"id": "p1", "a": "cat", "b": "dog"}]}' | jq .
# → 400: "requires an ~2048 MB runtime download ... set params.confirm_large_download=true
#    or ALLOW_LARGE_MODEL_DOWNLOADS=true"

# unblocked (per-request opt-in; or set ALLOW_LARGE_MODEL_DOWNLOADS=true once, server-side)
curl -s -X POST http://localhost:8000/v1/similarity/text/distance \
  -d '{"algorithm": "embedding_cosine",
       "params": {"variant": "fasttext", "confirm_large_download": true},
       "inputs": [{"id": "p1", "a": "cat", "b": "dog"}]}' | jq .
```

## Runtime resource requirements (CPU / RAM / GPU)

The [Resource gate](#resource-gate-for-large-downloads) only limits *downloads*
(disk space to cache weights). Every model-backed measure then needs **RAM to
load the model into memory** and **CPU or GPU cycles to run inference** on each
request — resources that are *separate from, and usually larger than*, the
download size. For a float32 model, the in-memory footprint is roughly **4× the
size of the downloaded file** (the safetensors file is already a compressed /
near-raw float32 dump; at load time there is an additional copy plus the
runtime/linear-algebra libraries), and PyTorch itself reserves several hundred
MB of RAM just for its CUDA/cuBLAS and CPU tensor kernels.

The base-tier measures (`wordnet_similarity`, `tfidf_cosine`,
`token_set_overlap`, `bm25`, lexical relations, DKPro sidecar) are **not**
listed here — they run comfortably on a small single-CPU host with a few
hundred MB of RAM. Only the optional `[model]` measures and the large gensim
embeddings need planning for **host compute**:

| Measure | Model (default) | Download | RAM to run (inference) | CPU vs. GPU |
|---|---|---|---|---|
| `sbert_cosine`, `semantic_search` | `all-MiniLM-L6-v2` (SBERT) | ~90 MB | ~0.5–1 GB | **CPU fine**; small model (22.7M params, 384-d), fast on a modern x86 core. GPU optional (adds speed, no gain in quality). |
| `sbert_cosine`, `semantic_search` | heavier SBERT via `params.model_name` (e.g. `all-mpnet-base-v2`, ~109M params) | ~420 MB | ~2–4 GB | CPU usable but slower; GPU recommended at higher throughput |
| `cross_encoder` | `cross-encoder/stsb-roberta-base` | ~440 MB | ~2–4 GB | Runs on CPU but is a full transformer pass per pair — **GPU recommended** for real-time/volume use; single pairs fine on CPU |
| `bertscore` | BERTScore's PyTorch transformer | several hundred MB | ~2–4 GB+ | Heaviest of the `[model]` measures — **GPU strongly recommended** (defaults to a large model); CPU possible but slow |
| `embedding_cosine` / `wmd` — `glove` | `glove-wiki-gigaword-50` | ~200 MB | ~0.5–1 GB | **CPU fine**; pure vector dot-product / WMD (CPU-bound) |
| `embedding_cosine` — `fasttext` | `fasttext-wiki-news-subwords-300` | ~2 GB download | **~4–8 GB RAM** to hold the 300-d matrix in memory | **CPU only** (no vector-GPU path used); WMD over this size is memory/CPU heavy |
| `embedding_cosine` — ConceptNet **local** | `conceptnet-numberbatch-17-06-300` | ~1.2 GB download | **~3–6 GB RAM** | **CPU only**; large matrix |
| `embedding_cosine` — ConceptNet **remote** | *(no local model)* | 0 MB, network-only | n/a (server-side) | Requires **network**, not local CPU/GPU — see [ConceptNet](#conceptnet-numberbatch-local-vs-remote) |

Three practical consequences, beyond download size:

- **RAM scales with model size, not download size.** A ~2 GB downloaded
  float32 gensim model needs ~4–8 GB of resident RAM once loaded — and it
  stays cached in `src/model_cache.py` for the life of the process. Loading
  several heavy models at once (e.g. fasttext **and** BERTScore) can exhaust
  a small server.
- **Inference is per-request CPU/GPU work.** `sbert_cosine`,
  `cross_encoder`, `bertscore` and `semantic_search` run the transformer
  forward pass once per input pair (per candidate for `semantic_search`).
  Throughput is bounded by CPU cores or GPU, *not* by bandwidth — these are
  not disk-bound; they are compute-bound.
- **The service is fully CPU-capable** (`requires_gpu: false` in the
  catalog): no measure *requires* a GPU; GPU only reduces latency/raises
  throughput for the heavy transformer measures. PyTorch (`[model]` extra)
  installs in CPU-only mode by default and uses the GPU automatically if one
  is present.

**Summary sizing guidance** for the optional `[model]` extra on a shared host:

- **Minimal** (`sbert_cosine` / `semantic_search` only, default MiniLM): ~2 CPU
  cores, 2 GB RAM, ~0.5 GB disk for the model — no GPU.
- **Recommended** (`cross_encoder` + `bertscore`): 4+ CPU cores, 8 GB RAM,
  ~1–2 GB disk; a small GPU (e.g. 4–8 GB VRAM) for interactive latency.
- **Heavy embeddings** (fasttext / ConceptNet Numberbatch local): 8–16 GB RAM
  and plentiful disk; CPU-only, no GPU benefit.

## `embedding_cosine`

Static/contextual word-vector cosine similarity, parameterised via
`params.variant` (a direct `params.model_name` always wins, so any
gensim-data model works without a new algorithm family):

```json
{"algorithm": "embedding_cosine", "params": {"variant": "fasttext"}}
```

| `variant` | Model | Notes |
|---|---|---|
| `glove` (default) | `glove-wiki-gigaword-50` | base, automatic |
| `fasttext` | `fasttext-wiki-news-subwords-300` | subword info, good for OOV/German compounds — gated |
| `conceptnet_numberbatch` | see below | two backends, `remote` default |

### ConceptNet Numberbatch: `local` vs `remote`

`params.backend` (inside `params`, distinct from the top-level `backend`
field) picks how this one variant is computed:

- **`remote`** *(default)* — calls the public ConceptNet API, which hosts a
  reduced Numberbatch matrix server-side. No local download, no `[model]`
  needed. See [External API dependencies](#external-api-dependencies) for
  limits and failure handling.
- **`local`** — the original gensim path: downloads/caches the ~1.2 GB model
  (gated, see above). `params.model_name` overrides apply only here.

There is **no silent fallback** between the two — a failed `remote` call
never falls back to `local`, since that would trigger a 1.2 GB download the
caller didn't ask for.

`glove` and `fasttext` are **local-only**: neither Stanford NLP nor
Meta/fasttext.cc host a public similarity API, so `params.backend: "remote"`
on those variants is rejected with `400`. This pattern does not generalize to
other variants.

## External API dependencies

`conceptnet_numberbatch` with `backend: "remote"` calls a public, third-party
API — the same kind of external dependency as the DKPro sidecar, just
off-host instead of a sidecar.

| | |
|---|---|
| Endpoint | `GET https://api.conceptnet.io/relatedness?node1=/c/{lang}/{a}&node2=/c/{lang}/{b}` |
| Auth | none |
| Rate limit | 3600 req/hour sustained, 120 req/min burst — outside our control |

Safeguards in `src/conceptnet_api.py`: ~5s per-request timeout; batch cap of
`CONCEPTNET_MAX_REMOTE_INPUTS` (default 60) inputs per request, rejected
up-front with `400` above that; throttling via
`CONCEPTNET_REMOTE_REQUEST_DELAY` (default 0.05s) between calls; backoff
retries on HTTP 429. Failures return `503` (timeout/network/429-after-retries)
or `502` (other upstream errors) — never a silent fallback to `local`.

Words are normalized to ConceptNet URIs (spaces → underscores);
`params.lang` overrides the default `en`.

## Token-set overlap: Jaccard / Dice

`jaccard = |A∩B|/|A∪B|` and `dice = 2|A∩B|/(|A|+|B|)` are monotone
transformations of each other (`dice = 2·jaccard/(1+jaccard)`) — same ranking,
different scale. One algorithm, `token_set_overlap`, with `params.variant`
(`jaccard` default, or `dice`); pure Python, base tier, deterministic
(lowercase + whitespace tokenizer). Empty/empty scores `1.0`; one empty side
scores `0.0`. The legacy names `jaccard`/`dice` remain as aliases
(`alias_of: token_set_overlap` in `/v1/similarity/text/algorithms`) for existing
consumers.

```sh
curl -s -X POST http://localhost:8000/v1/similarity/text/distance \
  -d '{"algorithm": "token_set_overlap", "params": {"variant": "dice"},
       "inputs": [{"id": "p1", "a": "the cat is here", "b": "the cat is there"}]}' | jq .
```

## BM25

Pure-stdlib BM25 retrieval on `/v1/similarity/text/retrieval` — the sole base-tier
retrieval algorithm (the former TF-IDF fallback backend of `semantic_search`
was removed; `semantic_search` is now `[model]`-only via
sentence-transformers). Same `matches`/`count` response shape as
`semantic_search`. Params: `k1` (1.5), `b` (0.75), `top_k` (10).

```sh
curl -s -X POST http://localhost:8000/v1/similarity/text/retrieval \
  -d '{"algorithm": "bm25", "params": {"top_k": 3},
       "inputs": [{"id": "q1", "query": "cat", "candidates": ["a cat", "a dog", "house"]}]}' | jq .
```

## Odenet (German lexical relations)

`synonym`/`antonym`/`hypernym`/`hyponym` support an `odenet` backend (Open
German WordNet — used instead of GermaNet, whose license restricts commercial
use), via the [`wn`](https://github.com/goodmami/wn) library.

```json
{"algorithm": "synonym", "backend": "odenet", "params": {}, "inputs": [{"id": "w1", "word": "Hund"}]}
```

Results carry `resource: "odenet:1.4"`. Coverage: synonym/hypernym/hyponym
well populated; antonym present but sparse. A word with no relation returns
`count: 0`, never an error.

## DKPro sidecar (optional)

`topic_model`, `structural_stylistic`, plus optional `backend: "dkpro"`
variants of `tfidf_cosine`/`wordnet_similarity`, are served by a separate
Java process in [`dkpro-sidecar/`](dkpro-sidecar/) over HTTP. Everything else
works without it; a DKPro-backed request returns `502/503 problem+json` when
the sidecar isn't running. Requires building DKPro Similarity from source
(JDK 21 + Maven) — enable only if those two measures are a hard requirement.

## Development

```sh
make prep    # install dependencies
make test    # run tests
make lint    # run ruff
make start   # run uvicorn on :8000
```

Test-suite notes (also enforced in CI):

- Default addopts (`pyproject.toml`) deselect the `model_download` and
  `network` markers, so the offline, no-PyTorch path is what `make test` runs:
  `pytest -m "not model_download and not network"`.
- Deselection is the responsibility of `-m`. **An explicit `-m` on the CLI
  replaces (does not merge with) the `addopts -m`.** If you narrow the filter
  (e.g. to `-m "not model_download"`), the `network` tests — which hit the
  real `api.conceptnet.io` — will run and fail intermittently on a live 502.
  Keep both markers in any override: `-m "not model_download and not network"`.
- The WordNet-backed measures need the small NLTK corpora
  (`wordnet`, `wordnet_ic`). `tests/conftest.py` downloads them automatically
  on first run, so a fresh checkout passes without manual data setup.
- Both profiles are covered. The fast base tests run under the default `cpu`
  profile; catalog/profile-guard assertions for `pytorch` use the `profile_client`
  fixture (`tests/conftest.py`), which reloads the app under a given
  `SIMILARITY_PROFILE` and restores `cpu` afterward.
- The **`text-similarity-pytorch` build** is end-to-end tested by
  `tests/test_async.py::TestPytorchProfileCompute` (real SBERT/cross-encoder
  requests through the `pytorch` profile). They need the `model` extra and a
  model download, so they carry the `model_download` marker — run them with
  `pip install -e ".[model]"` then `pytest -m "model_download and not network"`.
  CI's `pytorch-test` job runs exactly these.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SIMILARITY_PROFILE` | `cpu` | Build/run variant: `cpu` (default, PyTorch algorithms excluded) or `pytorch` (all algorithms). Baked into each image (see [Build variants](#build-variants-1-repo-%E2%86%92-2-images)) |
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | DKPro Java sidecar URL |
| `CONCEPTNET_API_URL` | `https://api.conceptnet.io` | ConceptNet relatedness API base URL |
| `CONCEPTNET_MAX_REMOTE_INPUTS` | `60` | Max inputs per request for `backend: remote` |
| `CONCEPTNET_REMOTE_REQUEST_DELAY` | `0.05` | Min seconds between ConceptNet API calls |
| `ALLOW_LARGE_MODEL_DOWNLOADS` | `false` | Server-wide opt-in for downloads > 500 MB — disk/RAM usage, not money (see [Resource gate](#resource-gate-for-large-downloads)) |

Data is never bundled into the image — everything downloads on first use and
is cached in `src/model_cache.py`. WordNet (NLTK), HuggingFace, Odenet and
gensim resources fetch automatically on first use; large ones (> 500 MB) only
after the cost-gate opt-in. In the images, the cache lives under the writable
`/var/text-similarity-cache` (set via `HOME`/`HF_HOME`/`GENSIM_DATA_DIR`/`NLTK_DATA`),
so the unprivileged `nobody` user can persist downloads across restarts.

## License

MIT
