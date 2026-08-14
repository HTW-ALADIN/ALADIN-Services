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

Two independent things keep the service cheap to run:

1. **Install tier** — only the PyTorch stack (`sentence-transformers`,
   `bert-score`) is an opt-in pip extra. Everything else (`nltk`,
   `scikit-learn`, `gensim`) is base. See [Installation tiers](#installation-tiers).
2. **Resource gate** — large *runtime* model downloads (> 500 MB) can't be
   triggered by accident; they need an explicit opt-in. "Cost" here means
   **disk/RAM/CPU resource usage on the server that hosts this service** —
   not a monetary or paid-tier cost. Nothing in this service requires
   payment; see
   [Resource gate for large downloads](#resource-gate-for-large-downloads).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/text/algorithms` | Discovery — list all algorithm/backend combinations with metadata |
| `POST` | `/v1/text/distance` | Compute text similarity (synchronous, batch) |
| `POST` | `/v1/text/retrieval` | Rank query candidates (synchronous, batch) |
| `POST` | `/v1/text/lexical` | Look up lexical relations (synchronous, batch) |

Every compute endpoint is synchronous and stateless: `algorithm` (+ optional
`backend`), `params`, and a batch `inputs` list in, one result per input out.
Omitted `backend` uses the algorithm's default (marked `default: true` in
`/v1/text/algorithms`).

## Algorithms

- **`/v1/text/distance`** — two texts in, one normalized score out:
  `wordnet_similarity`, `embedding_cosine`, `sbert_cosine`, `wmd`,
  `cross_encoder`, `tfidf_cosine`, `token_set_overlap` (variants `jaccard`/`dice`),
  `bertscore`, `topic_model`, `structural_stylistic`.
  Inputs: `{"id", "a", "b"}`.
- **`/v1/text/retrieval`** — query + candidates in, ranked matches out:
  `semantic_search` (`[model]`), `bm25` (base).
  Inputs: `{"id", "query", "candidates"}`.
- **`/v1/text/lexical`** — one word in, related words out:
  `synonym`, `antonym`, `hypernym`, `hyponym`.
  Inputs: `{"id", "word"}`.

  > `hypernym` and `hyponym` query the same WordNet/Odenet IS-A relation in
  > opposite directions (`dog` → `animal` vs. `dog` → `poodle`). Kept as
  > separate, self-documenting algorithm names — not merged.

## Example

```sh
curl -s -X POST http://localhost:8000/v1/text/distance \
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
command; same for `[de]`. `embedding_cosine`/`wmd` need no extra (`gensim` is
base) — their large downloads go through the resource gate instead (`400`, not
`501`).

```sh
pip install -e ".[model]"   # SBERT / BERTScore / semantic_search
pip install -e ".[de]"      # German lexical relations (Odenet)
python -m wn download odenet:1.4   # optional — auto-downloads on first use otherwise
```

Default image: `docker build -f Dockerfile -t text-similarity-service .` →
~800 MB (base deps incl. `gensim`, no PyTorch). Full stack:
`docker build --build-arg INSTALL_MODEL=true -t text-similarity-service .`
A BuildKit pip cache (`--mount=type=cache`) makes rebuilds with the model
stack cheap after the first time. Runtime model/data downloads are **never**
baked into the image, in either build.

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

```sh
# blocked
curl -s -X POST http://localhost:8000/v1/text/distance \
  -d '{"algorithm": "embedding_cosine", "params": {"variant": "fasttext"},
       "inputs": [{"id": "p1", "a": "cat", "b": "dog"}]}' | jq .
# → 400: "requires an ~2048 MB runtime download ... set params.confirm_large_download=true
#    or ALLOW_LARGE_MODEL_DOWNLOADS=true"

# unblocked (per-request opt-in; or set ALLOW_LARGE_MODEL_DOWNLOADS=true once, server-side)
curl -s -X POST http://localhost:8000/v1/text/distance \
  -d '{"algorithm": "embedding_cosine",
       "params": {"variant": "fasttext", "confirm_large_download": true},
       "inputs": [{"id": "p1", "a": "cat", "b": "dog"}]}' | jq .
```

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
(`alias_of: token_set_overlap` in `/v1/text/algorithms`) for existing
consumers.

```sh
curl -s -X POST http://localhost:8000/v1/text/distance \
  -d '{"algorithm": "token_set_overlap", "params": {"variant": "dice"},
       "inputs": [{"id": "p1", "a": "the cat is here", "b": "the cat is there"}]}' | jq .
```

## BM25

Pure-stdlib BM25 retrieval on `/v1/text/retrieval` — the sole base-tier
retrieval algorithm (the former TF-IDF fallback backend of `semantic_search`
was removed; `semantic_search` is now `[model]`-only via
sentence-transformers). Same `matches`/`count` response shape as
`semantic_search`. Params: `k1` (1.5), `b` (0.75), `top_k` (10).

```sh
curl -s -X POST http://localhost:8000/v1/text/retrieval \
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

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | DKPro Java sidecar URL |
| `CONCEPTNET_API_URL` | `https://api.conceptnet.io` | ConceptNet relatedness API base URL |
| `CONCEPTNET_MAX_REMOTE_INPUTS` | `60` | Max inputs per request for `backend: remote` |
| `CONCEPTNET_REMOTE_REQUEST_DELAY` | `0.05` | Min seconds between ConceptNet API calls |
| `ALLOW_LARGE_MODEL_DOWNLOADS` | `false` | Server-wide opt-in for downloads > 500 MB — disk/RAM usage, not money (see [Resource gate](#resource-gate-for-large-downloads)) |

Data is never bundled into the image — everything downloads on first use and
is cached in `src/model_cache.py`. Run `nltk.download('wordnet')` once for the
lexical measures; HuggingFace/Odenet/gensim resources fetch automatically
(large ones only after the cost-gate opt-in).

## License

MIT
