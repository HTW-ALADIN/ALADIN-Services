# text-similarity-service

**Semantic text similarity service** — measures how *similar the meaning* of
words, sentences and documents is, and looks up lexical relations
(synonym/antonym/hypernym/hyponym). 16 algorithm families over multiple
backends (NLTK, Odenet, sentence-transformers, gensim, scikit-learn, BERTScore,
DKPro Similarity, plus pure-Python measures).

**Character/string-level edit distances (Levenshtein, Jaro-Winkler, …) are out
of scope** — they live in the
[edit-distance-service](../edit-distance-service). This service focuses
exclusively on semantics:

```text
text-distance-service   = Character/String-level distances
text-similarity-service = Semantic/Lexical/Statistical similarity
```

**Lightweight by default.** The base install ships only `nltk` (~1.8 MB wheel +
WordNet corpus) and `scikit-learn` (~35-45 MB) — so the WordNet, TF-IDF,
token-set overlap (Jaccard/Dice variants) and BM25 families work out of the box. Everything that
needs a large model download (PyTorch-based SBERT/BERTScore, gensim word
vectors) is an **opt-in extra** (`pip install -e ".[model]"`); German lexical
lookups (Odenet) are a separate small **opt-in extra**
(`pip install -e ".[de]"`). See
[Model-based measures](#model-based-measures-optional) and
[Odenet (German lexical relations)](#odenet-german-lexical-relations).

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
  `cross_encoder`, `tfidf_cosine`, `token_set_overlap` (variants `jaccard` /
  `dice`; legacy aliases `jaccard`, `dice`), `bertscore`, `topic_model`,
  `structural_stylistic`). Inputs: `{"id", "a", "b"}`.
- **`/v1/text/retrieval`** (retrieval) — one query + candidates in, a ranked
  match list out (`semantic_search` — `[model]` only; `bm25` — base). Inputs:
  `{"id", "query", "candidates"}`.
- **`/v1/text/lexical`** (lexical_relations) — one word in, a set of related
  words out (`synonym`, `antonym`, `hypernym`, `hyponym`). Inputs:
  `{"id", "word"}`.

  > **`hypernym` vs `hyponym`:** both query the same WordNet/Odenet relation —
  > the IS-A hierarchy — in opposite traversal directions. `hypernym` walks
  > from a word to its more general terms (e.g. `dog` → `canine`, `animal`),
  > `hyponym` to its more specific terms (e.g. `dog` → `poodle`, `terrier`).
  > They are deliberately kept as separate algorithm names (established
  > NLP-community naming, self-documenting API) — no code combines or aliases
  > them.

## Semantic categories

`GET /v1/text/algorithms` describes each (operation, algorithm, backend)
combination with semantic metadata — not just library names. Every entry
carries `category`, `requires_model` and `requires_gpu` (always `false` — the
whole service is CPU-capable), plus `language`, `extra` (which pip extra
enables the backend) and `variants` where relevant:

| Category | Algorithms |
|---|---|
| `lexical` | `wordnet_similarity`, `synonym`, `antonym`, `hypernym`, `hyponym` |
| `statistical` | `tfidf_cosine`, `token_set_overlap` (variants `jaccard`/`dice`) |
| `word_embedding` | `embedding_cosine`, `wmd` |
| `sentence_embedding` | `sbert_cosine`, `cross_encoder` |
| `retrieval` | `semantic_search` (`[model]` only), `bm25` (base) |
| `evaluation` | `bertscore` |
| `topic` | `topic_model` (DKPro) |
| `structural` | `structural_stylistic` (DKPro) |

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
| **Base** (always) | `nltk`, `scikit-learn` (+ FastAPI stack) | WordNet similarity, TF-IDF, lexical relations (incl. `hyponym`), token-set overlap (`jaccard`/`dice` variants), `bm25` — **8/16** |
| **`[model]` extra** | `sentence-transformers`, `bert-score`, `gensim` (+ PyTorch) | `embedding_cosine` (glove/fasttext local; `conceptnet_numberbatch` local **or** remote API — the remote default needs no extra), `sbert_cosine`, `wmd`, `cross_encoder`, `bertscore`, `semantic_search` — **+6/16** |
| **`[de]` extra** | `wn` (small, pure Python, no PyTorch) | German lexical relations via Odenet (`synonym`, `antonym`, `hypernym`, `hyponym`, backend `odenet`) |
| **DKPro sidecar** | separate Java service | `topic_model`, `structural_stylistic` (routed) — **2/16** |

### Coverage table

| # | Family | Backend | Extra / Data |
|---|---|---|---|
| 1 | WordNet path/IC similarity (`wordnet_similarity`) | nltk (default) | base (WordNet corpus) |
| 2 | Synonym lookup | nltk (default), **odenet** (German) | base / `[de]` |
| 3 | Antonym lookup | nltk (default), **odenet** (German) | base / `[de]` |
| 4 | Hypernym lookup | nltk (default), **odenet** (German) | base / `[de]` |
| 5 | Hyponym lookup | nltk (default), **odenet** (German) | base / `[de]` |
| 6 | TF-IDF vector-space cosine (`tfidf_cosine`) | scikit-learn | base |
| 7 | Token-set overlap (`token_set_overlap`) — variants `jaccard` / `dice` (legacy aliases `jaccard`, `dice`) | builtin (pure Python) | base |
| 8 | BM25 retrieval (`bm25`) | builtin (pure Python) | base |
| 9 | Semantic search (`semantic_search`) | sentence-transformers | `[model]` (PyTorch) |
| 10 | Static word/doc embedding (`embedding_cosine`) — variants `glove` / `fasttext` (local gensim) and `conceptnet_numberbatch` (**two backends:** `local` via gensim, `remote` via api.conceptnet.io — `remote` default) | gensim (+ remote ConceptNet API for `conceptnet_numberbatch`) | `[model]` (+ model download **only** for `local`; `remote` needs no download) |
| 11 | Transformer sentence embedding (`sbert_cosine`) | sentence-transformers | `[model]` (PyTorch) |
| 12 | Word Mover's Distance (`wmd`) | gensim | `[model]` (+ GloVe download) |
| 13 | Contextual eval metric (`bertscore`) | bert-score | `[model]` (PyTorch) |
| 14 | Cross-encoder reranking (`cross_encoder`) | sentence-transformers | `[model]` (PyTorch) |
| 15 | Topic-model (`topic_model`) | dkpro (Java sidecar) | separate optional sidecar |
| 16 | Structural/stylistic (`structural_stylistic`) | dkpro (Java sidecar) | separate optional sidecar |

### Enabling optional stacks

```sh
pip install -e ".[model]"   # sentence-transformers + gensim + bert-score (+ PyTorch)
pip install -e ".[de]"      # German lexical relations via Odenet (wn, no PyTorch)
python -m wn download odenet:1.4   # once, for the [de] Odenet data (auto-downloaded on first use otherwise)
```

- Imports are **lazy** — the base service never loads PyTorch/gensim/wn unless a
  model-based algorithm is actually called.
- The models / data themselves (HuggingFace SBERT/BERTScore checkpoints, gensim
  GloVe/FastText/Numberbatch vectors, Odenet) are **downloaded on first use and
  cached** (`src/model_cache.py`), not bundled into the image.
- Without an extra, its endpoints return a clean `501 problem+json` naming the
  missing module and the correct install command (`.[model]` vs `.[de]`); all
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

## Token-set overlap: Jaccard / Dice (base)

Lightweight, deterministic, CPU-only, no model and no NLP dependency — the
tokenizer is a simple lowercase + whitespace split. One algorithm family
(`token_set_overlap`) with a `params.variant` selector, mirroring the
`embedding_cosine` variant pattern:

- `variant: "jaccard"` (default) — `|A ∩ B| / |A ∪ B|`
- `variant: "dice"` — `2|A ∩ B| / (|A| + |B|)`

The two normalisations are **monotone transformations of each other**
(`dice = 2·jaccard / (1 + jaccard)`), so they produce the same ranking for every
input pair — only the scale differs. Both run on the base install and are
listed under `category: statistical`. Empty/empty inputs score `1.0`, an empty
side scores `0.0`.

The legacy algorithm names `jaccard` and `dice` remain available as **aliases**
that map to the same handler with the variant pinned (see `/v1/text/algorithms`,
entries marked `alias_of: token_set_overlap`), so existing API consumers keep
working unchanged:

```sh
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "token_set_overlap", "params": {"variant": "dice"}, "inputs": [{"id": "p1", "a": "the cat is here", "b": "the cat is there"}]}' | jq .

# equivalent legacy aliases (fixed variant):
#   {"algorithm": "jaccard", ...}  ==  token_set_overlap, variant=jaccard
#   {"algorithm": "dice", ...}     ==  token_set_overlap, variant=dice
```

## BM25 (base)

Classic BM25 lexical retrieval for `POST /v1/text/retrieval` — pure stdlib
(~20 lines, no new dependency), CPU-only, deterministic. BM25 is the **sole
base-tier retrieval algorithm**: the former TF-IDF fallback backend of
`semantic_search` was removed, so `semantic_search` is now `[model]`-only
(sentence-transformers). Returns the same `matches`/`count` shape as
`semantic_search`. Parameters: `k1` (default 1.5), `b` (default 0.75),
`top_k` (default 10).

```sh
curl -s -X POST http://localhost:8000/v1/text/retrieval \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "bm25", "params": {"top_k": 3}, "inputs": [{"id": "q1", "query": "cat", "candidates": ["a cat", "a dog", "house"]}]}' | jq .
```

## Configurable static embedding variants (fasttext / conceptnet_numberbatch)

`embedding_cosine` is no longer tied to a single GloVe model. It is
parameterised exactly like the existing `params.model_name` mechanism — the
`variant` is just a convenience alias for a published gensim-data resource:

```json
{
  "algorithm": "embedding_cosine",
  "params": {"variant": "fasttext"}
}
```

| `variant` | gensim-data model | Notes |
|---|---|---|
| `glove` (default) | `glove-wiki-gigaword-50` | same as before — **local-only** |
| `fasttext` | `fasttext-wiki-news-subwords-300` | subword info — good for unknown/rare words, morphology, German — **local-only** |
| `conceptnet_numberbatch` | `conceptnet-numberbatch-17-06-300` (**local only**) | **two backends:** `local` (gensim download, ~1.2 GB) or `remote` (default — public api.conceptnet.io, no download). See below. |

- A direct `params.model_name` always wins over `variant` (on the `local`
  path), so any gensim-data model is selectable without a new algorithm family.
- Everything goes through the existing `get_gensim_model` cache: lazy load,
  one download per model, reused across requests.
- Models are downloaded at runtime and **never** committed or baked into the
  image.

### `conceptnet_numberbatch`: `local` vs `remote` backend

The `conceptnet_numberbatch` variant has **two execution backends**, selected
via `params.backend` — a parameter *inside* `params`, distinct from the
top-level `backend` field (which stays `gensim` for backward compatibility):

| `params.backend` | What happens | Default |
|---|---|---|
| `remote` | Calls the public ConceptNet API (`GET https://api.conceptnet.io/relatedness?node1=/c/{lang}/{a}&node2=/c/{lang}/{b}`), which hosts a reduced Numberbatch matrix server-side. **No local download**, no `[model]` extra needed. | ✅ default |
| `local` | Existing gensim behaviour: downloads/caches the ~1.2 GB `conceptnet-numberbatch-17-06-300` model. | opt-in |

```json
{
  "algorithm": "embedding_cosine",
  "params": {"variant": "conceptnet_numberbatch", "backend": "remote"},
  "inputs": [{"id": "p1", "a": "cat", "b": "dog"}]
}
```

- `remote` maps the API's `value` onto the usual result schema (`raw`,
  `similarity`, `distance`, `compute_time_ms`) and adds `source: "conceptnet_api"`
  so a result is traceable to the external API.
- Words are normalized to ConceptNet URIs: whitespace → underscores
  (`"cat in the hat"` → `/c/en/cat_in_the_hat`); `params.lang` overrides the
  default language code `en`.
- **`glove` and `fasttext` are local-only**: there is no public similarity API
  for them (neither Stanford NLP nor Meta/fasttext.cc host an inference
  endpoint), so `params.backend: "remote"` on those variants is rejected with a
  clean `400`. Do **not** assume this pattern transfers 1:1 to other variants.
- Explicit `params.backend: "local"` reproduces exactly the previous behaviour
  (including `params.model_name` overrides). With `remote`, `params.model_name`
  is ignored — the API exposes one fixed matrix.
- **No silent fallback:** if the ConceptNet API fails (timeout, network error,
  429 rate limit), the request returns a clean `502/503 problem+json` — it
  never silently falls back to `local` (which would trigger the 1.2 GB
  download). See [External API dependencies](#external-api-dependencies).

## Configurable sentence-transformers model (`model_name`)

`sbert_cosine`, `semantic_search` and `cross_encoder` already read
`params.model_name`; the existing defaults are unchanged (`all-MiniLM-L6-v2`
for SBERT/semantic search,
`cross-encoder/stsb-roberta-base` for the cross-encoder). There is no
per-model algorithm family:

```json
{
  "algorithm": "sbert_cosine",
  "params": {"model_name": "paraphrase-multilingual-MiniLM-L12-v2"}
}
```

Large models are opt-in through `model_name` and run on CPU; the service is
never optimised for (or specialised to) 7B-class LLM backbones. `bertscore`
is parameterised via `params.model_type` / `params.lang`.

## Odenet (German lexical relations)

German lexical relations are provided by the **Open German WordNet (Odenet)** —
a freely licensed German wordnet, used instead of GermaNet (whose license is
restrictive for commercial use). Odenet is exposed as an additional `odenet`
backend on `synonym` / `antonym` / `hypernym` / `hyponym`, selectable like any
other backend:

```json
{
  "algorithm": "synonym",
  "backend": "odenet",
  "params": {},
  "inputs": [{"id": "w1", "word": "Hund"}]
}
```

- Backend: the established [`wn`](https://github.com/goodmami/wn) Python
  library (`pip install -e ".[de]"`), mirroring the NLTK/WordNet path in
  `src/lexical.py`.
- Odenet data (`odenet:1.4`) is downloaded on first use via `wn` and cached;
  it is not committed and not in the image.
- Results include a `resource: "odenet:1.4"` field so the source of a relation
  is always traceable; the top-level `backend` field already distinguishes
  `nltk` vs `odenet` (results from different resources are never mixed
  silently).
- Relation coverage depends on the Odenet data: synonym/hypernym/hyponym are
  well populated; antonym is present but sparse (Odenet stores it at synset
  level — the service reads both synset- and sense-level antonyms). A word
  without a relation simply returns `count: 0`, never an error.
- Without the `de` extra, an Odenet request returns a clean `501 problem+json`
  naming `pip install -e ".[de]"`; without the data it auto-downloads.

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

## External API dependencies

One variant (`embedding_cosine` with `params.variant: "conceptnet_numberbatch"`
and `params.backend: "remote"`, the default) calls a **public, third-party
API** — analogous to the DKPro sidecar dependency, but external:

| | |
|---|---|
| Endpoint | `GET https://api.conceptnet.io/relatedness?node1=/c/en/{a}&node2=/c/en/{b}` |
| Purpose | hosts a reduced ConceptNet Numberbatch embedding matrix — replaces the local ~1.2 GB gensim download for this variant |
| Auth | none (no API key) |
| Rate limit | **3600 requests/hour** sustained, **120 requests/minute** burst |
| Control | ❌ **outside our control** — a free public service with no SLA |

Client-side protections (built into `src/conceptnet_api.py`):

- **Per-request timeout** (~5 s) — a slow/hung upstream fails fast instead of
  blocking a request.
- **Batch cap** — `backend: "remote"` accepts at most
  `CONCEPTNET_MAX_REMOTE_INPUTS` (default **60**) inputs per request; a single
  batch of ≤ 60 stays within the 120/min burst. Larger batches are rejected
  up-front with a clean `400` telling the caller to split the batch or use
  `backend: "local"`.
- **Throttling** — a minimum `CONCEPTNET_REMOTE_REQUEST_DELAY` (default 0.05 s)
  is enforced between consecutive remote calls, so one batch does not burn the
  3600/h sustained limit in seconds.
- **Backoff on 429** — rate-limit responses are retried a few times with
  exponential backoff before giving up.

Failure handling (mirrors the DKPro sidecar pattern — **no silent fallback**):

- Network error / timeout / HTTP 429 (after retries) → `503 problem+json`
- Other upstream HTTP errors / malformed response → `502 problem+json`
- The request **never** silently falls back to `backend: "local"` — doing so
  would trigger the 1.2 GB Numberbatch download without the caller's knowledge.

> ⚠️ Only `conceptnet_numberbatch` has a remote API. **`glove` and `fasttext`
> have NO public similarity API** (neither Stanford NLP nor Meta/fasttext.cc
> host an inference endpoint) and remain local gensim downloads. A later
> maintainer must not assume this pattern transfers 1:1 to other variants.

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
| `CONCEPTNET_API_URL` | `https://api.conceptnet.io` | Base URL of the public ConceptNet relatedness API (`params.backend: "remote"`) |
| `CONCEPTNET_MAX_REMOTE_INPUTS` | `60` | Max inputs per request for `backend: "remote"` (rate-limit guard, see [External API dependencies](#external-api-dependencies)) |
| `CONCEPTNET_REMOTE_REQUEST_DELAY` | `0.05` | Min seconds between consecutive ConceptNet API calls (client-side throttle) |

## Data Dependencies

Data is never bundled into the image; it is downloaded on first use and cached
in memory (`src/model_cache.py`). Sizes and requirements:

| Data | Size | Needed by | Extra? |
|------|------|-----------|--------|
| NLTK WordNet corpus | ~12 MB download / ~35 MB unpacked | `wordnet_similarity`, `synonym`, `antonym`, `hypernym`, `hyponym` | — (small runtime download, base install) |
| NLTK Information Content corpus | small | `wordnet_similarity` variants `res`/`jcn`/`lin` | — |
| Odenet (`odenet:1.4`) | small (~10-30 MB) | German `synonym`/`antonym`/`hypernym`/`hyponym` via `backend: odenet` | ✅ `[de]` (`wn` library) |
| HuggingFace models (SBERT `all-MiniLM-L6-v2`, cross-encoder, BERTScore) | 100–400 MB each | `sbert_cosine`, `cross_encoder`, `bertscore`, `semantic_search` | ✅ `[model]` |
| gensim GloVe vectors (`glove-wiki-gigaword-50`) | ~200 MB | `embedding_cosine` (glove), `wmd` | ✅ `[model]` |
| gensim FastText vectors (`fasttext-wiki-news-subwords-300`) | ~2 GB | `embedding_cosine` variant `fasttext` | ✅ `[model]` |
| gensim ConceptNet Numberbatch (`conceptnet-numberbatch-17-06-300`) | ~1.2 GB | `embedding_cosine` variant `conceptnet_numberbatch` — **only with `params.backend: "local"`** (the `remote` default uses the public api.conceptnet.io API instead, no download) | ✅ `[model]` |

Run `nltk.download('wordnet')` once for the lexical measures. The HuggingFace,
gensim and Odenet resources are fetched automatically on first use when the
corresponding extra (`[model]` / `[de]`) is installed.

## License

MIT
