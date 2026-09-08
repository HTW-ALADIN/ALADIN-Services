# ADR-0001: ConceptNet Numberbatch as an optional sidecar process

- Status: accepted
- Date: 2026-08-20
- Context: `text-similarity-service`

## Context

The `embedding_cosine` algorithm, variant `conceptnet_numberbatch`, `backend: local`
currently runs the local gensim ConceptNet Numberbatch model **inside the main
service process**. Numberbatch is ~1.2 GB on disk and needs ~3-6 GB of RAM once
loaded into a `gensim.KeyedVectors`. It is rarely requested, but because it is a
resident singleton in the `text-similarity-conceptnet` image, every process built
from that image holds that RAM permanently — even when no request has ever asked
for it. The idle-RAM footprint is the explicit problem this ADR resolves.

The same service already runs DKPro as an **optional Java sidecar**
(`TEXT_SIMILARITY_DKPRO_URL`, default `http://localhost:8100`): the Python main
service calls it over HTTP on demand, and when the sidecar is absent it answers
`502/503` instead of crashing or computing locally. Critically, the DKPro sidecar
works with **any** main image (`cpu`/`hf`), fully decoupled from the image tiering.

## Decision

1. **ConceptNet Numberbatch runs as its own optional sidecar process**
   (`services/conceptnet-sidecar/`, pure Python + gensim), reachable over HTTP at
   the URL in `TEXT_SIMILARITY_CONCEPTNET_URL` (default `http://localhost:8200`),
   structurally and semantically analogous to the DKPro sidecar. This isolates the
   multi-GB RAM overhead from the main service process, gives the model an
   independent lifecycle, and follows the proven DKPro pattern.

2. **The `text-similarity-conceptnet` image tier is removed.** The local Numberbatch
   model moves into the sidecar's own container. `text-similarity-hf` becomes the
   single "full feature" main build. The main service no longer downloads or loads
   the Numberbatch weights at all — it only holds a thin HTTP client.

3. **The sidecar loads the model lazily (not at process start) and evicts it after an
   inactivity TTL.** An idle process must not pin ~3-6 GB of RAM for a model nobody
   requested. The sidecar loads on first use, tracks `last_used`, and drops the model
   (setting it to `None` and calling `gc.collect()`) once it has been idle for
   `CONCEPTNET_IDLE_TTL_SECONDS` (default 900 s). An optional
   `CONCEPTNET_PRELOAD_ON_START=true` exists for deployments that prefer to pay the
   RAM cost upfront in exchange for a cold, un-delayed first request — this trade-off
   is explicit and documented, not the default.

4. **Backward compatibility for existing clients.** Requests with
   `{"algorithm": "embedding_cosine", "params": {"variant": "conceptnet_numberbatch",
   "backend": "local"}}` keep their **identical response shape**. Only the internal
   path changes: the main service now forwards to the sidecar over HTTP instead of
   computing locally. The main service's response envelope (raw/similarity/distance)
   is produced exactly as before.

## Consequences

- **Positive**: idle RAM of the main service no longer grows with an unused Numberbatch
  model; the heavy model is isolated and can be scaled independently; the sidecar works
  with *both* main images (`cpu`/`hf`), eliminating the separate `conceptnet` tier.
- **Negative**: a locally-started deployment without the sidecar answers
  `embedding_cosine` / `conceptnet_numberbatch` / `local` with `502/503` until
  `TEXT_SIMILARITY_CONCEPTNET_URL` is configured or the sidecar is started.
- **Trade-off**: the shared model RAM is not free — it lives in the sidecar process
  instead. The lazy-load + TTL eviction means it is only paid in the moments a request
  is actually in flight.
- **Migration**: any running `text-similarity-conceptnet` container is replaced by
  `text-similarity-hf` **plus** the `conceptnet-sidecar` container, with
  `TEXT_SIMILARITY_CONCEPTNET_URL` set for the main service.
