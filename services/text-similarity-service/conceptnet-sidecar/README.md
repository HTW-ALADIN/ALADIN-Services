# conceptnet-sidecar

> ⚠️ **OPTIONAL component.** This Python sidecar serves the local gensim ConceptNet
> Numberbatch model to the [text-similarity-service](../text-similarity-service) —
> `embedding_cosine` / `conceptnet_numberbatch` / `params.backend: local`. It is
> **not required** for normal operation: with the sidecar absent, those requests
> return `502/503` and every other algorithm keeps working.

**Why a separate process?** The ~1.2 GB / ~3-6 GB RAM model used to be loaded
in-process, pinning RAM in every full-feature container even when nobody asked for
it. Moving it to an isolated process (like the DKPro sidecar) decouples its life and
memory from the main service, and lets it work with **either** main image (`cpu`/`hf`).
See [ADR-0001](../text-similarity-service/docs/adr/0001-conceptnet-as-sidecar.md).

## Purpose

An internal sidecar, not a public API. The main `text-similarity-service` calls its
`POST /v1/relatedness` endpoint, which returns raw cosine similarity in `[-1, 1]`;
normalization to `[0,1]` happens in the main service so this process stays dumb and
replaceable.

## Lazy-load + idle TTL

The model is **not** loaded at startup. It loads on the first `/v1/relatedness`
request and is evicted from RAM (set to `None` + `gc.collect()`) after
`CONCEPTNET_IDLE_TTL_SECONDS` (default 900 s) of inactivity. So an idle sidecar sits
at **< 200 MB**, not ~3-6 GB — this is the whole point of the separate process. A
request after an eviction re-loads the model automatically; that single call just
takes longer (expected, documented behavior, not a bug).

## Endpoints

- `GET /health` — liveness, always 200 once the process is up (independent of model state)
- `GET /health/ready` — 200 if the model is loaded **or** would lazy-load on demand; 503 only on a real error (missing model file/path)
- `POST /v1/relatedness` — `{"pairs":[{"id","word_a","word_b","lang"}]}` → `[{"id","score"|"error"}]`. OOV words yield `score: null` + `error: "oov: <word>"` for that pair, never a batch-wide failure.
- `GET /v1/status` — `{"model_loaded","loaded_at","idle_seconds","ttl_seconds"}` for monitoring the lazy-load/TTL behavior.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CONCEPTNET_MODEL_PATH` | *(required)* | Path to the Numberbatch KeyedVectors file. Errors surface at the **first load attempt** (as 503), not at start, so missing models never mask liveness. |
| `CONCEPTNET_IDLE_TTL_SECONDS` | `900` | Idle seconds before the loaded model is evicted from RAM. |
| `CONCEPTNET_EVICTION_CHECK_INTERVAL_SECONDS` | `60` | How often the background task checks for an idle model. |
| `CONCEPTNET_PRELOAD_ON_START` | `false` | If true, load the model synchronously at start (no lazy load). Trade-off: the first request is never delayed, but you pay ~3-6 GB RAM permanently. |

## Development

```sh
make prep                                            # install deps
CONCEPTNET_MODEL_PATH=/path/to/conceptnet-numberbatch-17-06-300 make test
CONCEPTNET_MODEL_PATH=/path/to/conceptnet-numberbatch-17-06-300 make start   # uvicorn on :8200
make docker-build                                    # build the image
```

## License

MIT
