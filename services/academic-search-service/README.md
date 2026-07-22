# academic-search-service

Unified search / export / download / citation-graph API over
[`academic-mcp`](https://pypi.org/project/academic-mcp/) and
[`scimesh`](https://github.com/gabfssilva/scimesh), with credentials supplied
per-request rather than baked into deployment config.

- Search across multiple providers in one call (arXiv, OpenAlex, Semantic
  Scholar, Scopus via `scimesh`; PubMed, PMC, bioRxiv, medRxiv, CrossRef,
  CORE, IEEE, Springer, ScienceDirect, Web of Science, ACM, JSTOR,
  ResearchGate, Google Scholar, IACR via `academic-mcp`).
- Optional cross-provider deduplication with a statistics/report breakdown.
- Export to BibTeX, RIS, CSV, or JSON.
- Bounded-batch PDF download and full-text extraction.
- Citation graph construction from seed papers (forward/backward/both),
  paginated one BFS level per call via a stateless, signed cursor -- no job
  queue, no persistent graph store.
- HTTP API (FastAPI) and CLI (Typer), sharing the same `core/*` logic.

See `unified-api-implementation-plan.md` and
`repo-integration-implementation-plan.md` in this directory for the full
design rationale.

## Code Layout

```text
src/main.py                     FastAPI app factory
src/config.py                   Env-driven configuration (no credentials)
src/generate_openapi.py         Writes academic-search-service.openapi.json
src/api/routes/                 HTTP routes (health, search, export, download, graph)
src/api/schemas/                Pydantic request/response models
src/core/paper.py                Canonical Paper schema + identifier-priority hashing
src/core/credentials.py          Per-request Credential Resolver
src/core/url_safety.py           SSRF-safety checks for provider-returned URLs
src/core/provider_registry.py    Provider -> backend routing table
src/core/pagination.py           HMAC-signed graph pagination cursor
src/core/query.py                Structured SearchQuery -> per-backend query translation
src/core/search_service.py       Search orchestrator (fan-out + dedup)
src/core/graph_service.py        Paginated citation-graph BFS
src/core/download_service.py     Bounded-batch download logic
src/core/fulltext_service.py     Full-text extraction (academic-mcp only)
src/adapters/                   scimesh / academic-mcp backend adapters
src/dedup/engine.py               Tiered cross-provider deduplication
src/export/                     BibTeX / RIS / CSV / JSON serializers
src/cli/                        Typer CLI mirroring the HTTP API 1:1
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | HTTP host to bind |
| `PORT` | `8003` | HTTP port used by `make start` and the Docker container |
| `LOG_LEVEL` | `info` | Log verbosity |
| `GRAPH_CURSOR_SECRET` | random per-process | HMAC signing key for `/v1/graph` pagination cursors. **Set this explicitly to a stable secret in any real deployment** -- if left unset, cursors stop validating across restarts/replicas. |
| `DOWNLOAD_MAX_BATCH_SIZE` | `20` | Max `items` per `/v1/download` call; larger batches must be paginated client-side |

No provider API keys/tokens are configured via environment variables. All
provider credentials (`SCOPUS_API_KEY`-equivalents, `mailto`, etc.) are
supplied **per request**, in the `credentials` object of the request body (or
the CLI's `--credentials` flag) -- see the API section below.

## Security Disclaimer: authentication is NOT provided by this service

**This service has no built-in authentication or authorization on any of its
HTTP endpoints** (`/v1/search`, `/v1/export`, `/v1/download`, `/v1/fulltext`,
`/v1/graph`). Anyone who can reach the service over the network can invoke it,
including causing it to make outbound requests (to academic provider APIs, and
to PDF/full-text URLs returned by those providers) using caller-supplied
credentials.

**Securing access to this service is a deployment-time obligation delegated
to whoever runs/embeds it** -- the consuming system, workflow orchestrator, or
platform team deploying this service is responsible for placing it behind an
appropriate auth boundary before it is reachable from anything other than a
fully trusted network. Suitable options include (non-exhaustive):

- Only binding/exposing the service on a private network segment reachable
  exclusively by the trusted workflow system that calls it.
- Fronting it with an API gateway, reverse proxy, or service mesh that
  enforces authentication (API keys, mTLS, OAuth2/OIDC, network policies)
  before requests reach this service.
- Wrapping it in an authenticating sidecar/proxy if the deployment platform
  does not offer the above natively.

Two related mitigations exist in the service itself, but neither is a
substitute for an auth boundary:

- Any URL this service fetches server-side that originated from a
  provider's response (e.g. a paper's `pdf_url`) is checked by
  `src/core/url_safety.py` (rejects loopback, link-local, RFC1918 private
  ranges, and known cloud metadata endpoints) before the request is made.
  This is a best-effort, static hostname/IP-literal check -- it does not
  resolve DNS, and does not prevent requests to arbitrary **public** URLs.
  **Known gap:** this check only covers the `scimesh`-backed download path
  (`core/download_service.py`'s `_download_via_scimesh`). For
  academic-mcp-backed providers, the PDF fetch happens entirely inside the
  vendored `academic-mcp` library with no interception point currently
  available, so that path is **not** SSRF-checked by this service.
- `paper_id` values supplied to `/v1/download` and `/v1/fulltext` are
  validated by `src/core/identifiers.py` to reject path-traversal patterns
  (`..` segments, absolute paths, backslashes) before being forwarded to any
  backend, since several `academic-mcp` searchers build a filesystem path
  directly from the identifier.
- Credentials are never logged (see `core/credentials.py`'s `redact()`),
  never persisted to disk, and never returned in a `Paper.raw` payload.

**Do not expose this service on an untrusted network without first adding an
authentication layer in front of it.**

## API

Start the service:

```sh
make start
```

The API listens on port `8003` by default. OpenAPI docs: `http://localhost:8003/docs`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `POST` | `/v1/search` | Search across multiple providers, with optional dedup |
| `POST` | `/v1/export` | Export a paper list to BibTeX/RIS/CSV/JSON |
| `POST` | `/v1/download` | Download a bounded batch of PDFs |
| `GET` | `/v1/fulltext` | Extract full text for a single paper (academic-mcp providers only) |
| `POST` | `/v1/graph` | Paginated citation-graph expansion (one BFS level per call) |

### Example: search

```sh
curl -X POST http://localhost:8003/v1/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"text": "graph neural networks", "year": {"gte": 2022}},
    "providers": ["openalex", "arxiv"],
    "credentials": {"openalex": {"mailto": "team@example.org"}},
    "dedup": {"enabled": true}
  }'
```

### Example: paginated citation graph

```sh
# First call: no cursor, must include seeds
curl -X POST http://localhost:8003/v1/graph \
  -H 'Content-Type: application/json' \
  -d '{"seeds": [{"provider": "openalex", "paper_id": "10.1038/nphys1170"}], "max_depth": 2}'

# Subsequent calls: pass back the returned cursor until "done": true
curl -X POST http://localhost:8003/v1/graph \
  -H 'Content-Type: application/json' \
  -d '{"cursor": "<token from previous response>"}'
```

## CLI

```sh
uv run python -m cli search --query '{"text": "graph neural networks"}' \
    --providers openalex,arxiv \
    --credentials '{"openalex": {"mailto": "team@example.org"}}' > results.json

uv run python -m cli export --input results.json --format bibtex > out.bib

uv run python -m cli download --items '[{"provider": "arxiv", "paper_id": "2401.00001"}]'

uv run python -m cli graph --seeds '[{"provider": "openalex", "paper_id": "10.1038/nphys1170"}]' \
    --max-depth 2
```

The CLI's `graph` command loops internally over `/v1/graph`'s pagination until
`done`, so CLI users get a single fully-expanded result; the HTTP API stays
paginated for programmatic callers who want incremental results.

## Known Limitations

- **No persistent paper store.** `/v1/export` operates on an inline `papers`
  array (the output of a previous `/v1/search` or `/v1/graph` call), not a
  `paper_ids` lookup -- there is nowhere for this stateless service to look
  ids up from.
- **Citation-graph expansion is scimesh-only.** `academic-mcp`'s searchers
  expose a citation *count* on search results but not a citation graph API, so
  only `openalex`, `semantic_scholar`, and `scopus` (the `scimesh`-backed
  providers with `Provider.citations()` support) can be expanded in
  `/v1/graph`; other providers can still appear as unexpandable seed/leaf
  nodes.
- **CrossRef is not routed through `scimesh`.** The installed `scimesh`
  version (0.3.0) does not yet ship a CrossRef provider; CrossRef search goes
  through `academic-mcp` only.
