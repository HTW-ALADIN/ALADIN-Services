# Repository Integration Implementation Plan

Companion to `unified-api-implementation-plan.md`. That document defines *what* the
API does; this document defines *how* `academic-search-service` must be structured,
built, tested, and shipped so it fits the surrounding `ALADIN-Functions` monorepo the
same way the other five services do.

Derived from analysis of the repo root (`README.md`, root `Makefile`,
`.github/workflows/`, `packages/`) and the existing services, in particular
`fermentaladin-service` (closest analog: Python + FastAPI + `uv`, no built-in job
queue/object storage) and `llm-gateway-service` (closest analog for *behavior*:
multi-provider passthrough, per-request credentials, explicit no-built-in-auth
security disclaimer).

Decisions confirmed with the user for this plan:

- **Stack**: Python + FastAPI + `uv`, mirroring `fermentaladin-service` exactly —
  required anyway since every underlying library (`academic-mcp`, `scimesh`,
  `pyalex`, `habanero`, `semanticscholar`, `arxiv.py`, `Bio.Entrez`) is Python-only.
- **Interface**: HTTP **and** CLI (this service is the first Python service in the
  repo with a CLI; see §4).
- **Downloads & citation graphs**: no new infra (no object storage, no job
  queue/worker). Batch downloads and multi-level graph expansion are handled via
  **client-driven pagination/cursor semantics** instead of server-tracked background
  jobs (see §5) — replacing the async-job design sketched in
  `unified-api-implementation-plan.md` §7/§8.
- **Security stance**: adopt `llm-gateway-service`'s "no built-in auth is a
  deployment-time obligation" disclaimer, plus SSRF-safety checks on any
  provider-returned URL this service fetches server-side (see §7).

---

## 1. Directory Layout

Follow the root `README.md`'s documented contract exactly:

```
services/academic-search-service/
├── src/
│   ├── main.py                      # FastAPI app factory + uvicorn entrypoint
│   ├── config.py                    # Env-driven settings (pydantic-settings)
│   ├── generate_openapi.py          # Writes academic-search-service.openapi.json
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py            # GET /health
│   │   │   ├── search.py            # POST /v1/search
│   │   │   ├── export.py            # POST /v1/export
│   │   │   ├── download.py          # POST /v1/download, GET /v1/papers/{id}/fulltext
│   │   │   └── graph.py             # POST /v1/graph (paginated, see §5)
│   │   └── schemas/                 # Pydantic request/response models (mirrors
│   │                                 # the canonical Paper schema from the API plan)
│   ├── core/
│   │   ├── paper.py                 # Canonical Paper model + identifier-priority hashing
│   │   ├── credentials.py           # Credential Resolver (§7)
│   │   ├── url_safety.py            # SSRF-safety checks for provider-returned URLs (§7)
│   │   ├── provider_registry.py     # Provider → backend routing table (§3 of API plan)
│   │   └── pagination.py            # Opaque cursor encode/decode helpers (§5)
│   ├── adapters/
│   │   ├── scimesh_adapter.py       # Wraps scimesh Provider/search/citations calls
│   │   └── academic_mcp_adapter.py  # Wraps academic-mcp paper_search/download/read
│   ├── dedup/
│   │   └── engine.py                # Tiered matching + merge policy + report (§6 of API plan)
│   ├── export/
│   │   ├── bibtex.py
│   │   ├── ris.py
│   │   ├── csv.py
│   │   └── json.py
│   └── cli/
│       ├── __init__.py              # Typer app, mirrors the HTTP API 1:1
│       └── commands/
│           ├── search.py
│           ├── export.py
│           ├── download.py
│           └── graph.py
├── test/
│   ├── api/                         # Endpoint-level tests (httpx.AsyncClient / TestClient)
│   ├── adapters/                    # Adapter tests against recorded/mocked provider responses
│   ├── dedup/
│   ├── export/
│   └── cli/
├── http-tests/                      # .http smoke-test files, matching fermentaladin-service
│   ├── health.http
│   ├── search.http
│   ├── export.http
│   ├── download.http
│   └── graph.http
├── Dockerfile
├── docker-compose.yml               # optional; only if local dev needs anything beyond the app itself
├── Makefile
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example                     # renamed from fermentaladin's .demo.env for clarity; see §7
├── .dockerignore
├── .gitignore
├── academic-search-service.openapi.json   # generated artifact, committed like the other services
└── README.md
```

This mirrors `fermentaladin-service`'s `src/`-rooted layout (not `src/api/` at the
top like the TypeScript services use `src/api/index.ts`), since `uvicorn ... --app-dir
src` is the established Python convention in this repo. The `cli/` package is new for
Python here, modeled on the *shape* of `llm-gateway-service/src/cli/` (Commander) and
`jsonpath-mapper-service/src/cli.ts`, adapted to `Typer` (the de-facto standard
CLI framework for FastAPI-adjacent Python projects; add it as a new dependency).

---

## 2. Build Tooling & `pyproject.toml`

Match `fermentaladin-service`'s toolchain choices so the root Makefile, CI runner
image, and any future shared Python packages behave uniformly across both Python
services:

- **Package manager**: `uv` (`uv sync`, `uv run`, `uv.lock` committed).
- **Linter/formatter**: `ruff` (`ruff check`, `ruff format --check`).
- **Test runner**: `pytest` with `pytest-cov` (`--cov=src --cov-report=xml
  --cov-report=term-missing`), `pytest-asyncio` for the async adapters/routes.
- **HTTP client**: `httpx` (already the async client both `academic-mcp` and
  `scimesh` build on).
- **CLI framework**: `Typer` (new dependency, not yet used elsewhere in the repo —
  flagged in §8 as an open question in case the team prefers `click` directly for
  consistency-with-nothing-in-particular; `Typer` is chosen here because it generates
  `--help` or JSON I/O commands with the least boilerplate and pairs naturally with
  the Pydantic models already needed for the FastAPI schemas).
- **Python version**: `3.12`, matching `fermentaladin-service`'s `.python-version`
  and Dockerfile base (`python:3.12-slim-trixie`).

`pyproject.toml` should declare `academic-mcp` and `scimesh` as regular dependencies
(pinned to the versions verified in `academic-database-libraries-overview.md`:
`academic-mcp>=0.1.7`, `scimesh>=0.3.0`), plus per-provider extras if either library
supports optional extras for paywalled providers (verify against each library's
actual `pyproject.toml`/`extras_require` during Phase 1 implementation — not yet
confirmed from the overview doc alone).

---

## 3. Makefile Contract

Implement exactly the eight targets the root `README.md` mandates, following
`fermentaladin-service/Makefile` as the template, plus wiring the CLI's own
entrypoint into `start`/testing where relevant:

```makefile
IMAGE_NAME  := academic-search-service
OPENAPI_OUT := academic-search-service.openapi.json
PORT        ?= 8003

.PHONY: prep build test lint start cli clean docker-build generate-openapi

prep:
	uv sync

build:
	@echo "No build step required for Python"

test:
	uv run pytest --cov=src --cov-report=xml --cov-report=term-missing

lint:
	uv run ruff check src/ test/
	uv run ruff format --check src/ test/

start:
	uv run uvicorn main:app --reload --port $(PORT) --app-dir src

cli:
	uv run python -m cli --app-dir src

clean:
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t $(IMAGE_NAME) .

generate-openapi:
	uv run python src/generate_openapi.py
```

`cli` is an addition beyond the mandated eight targets (the root Makefile contract is
a minimum, not a ceiling — `llm-gateway-service` similarly adds an `npm run cli`
script outside the Makefile's mandated set). Pick an unused port (`8003`) — confirm
against the other four services' chosen ports (`8000` fermentaladin, `8002`
llm-gateway) before implementation to avoid collision if more services have been
added since this plan was written.

---

## 4. CLI Design

Mirrors the HTTP API 1:1, matching the stated goal for `llm-gateway-service`'s CLI
("mirrors the API and is the primary way this service is invoked from workflows —
JSON in, JSON out"):

```
academic-search search --query '{"text": "..."}' --providers openalex,arxiv \
    --credentials '{"openalex": {"mailto": "..."}}' [--dedup] > results.json

academic-search export --input results.json --format bibtex > out.bib

academic-search download --paper-ids id1,id2 --prefer pdf --out-dir ./downloads

academic-search graph --seeds doi1,doi2 --direction both --max-depth 2 \
    --max-nodes-per-level 100 [--cursor <token>]   # see §5 for pagination
```

- Each subcommand is a thin wrapper that constructs the same Pydantic request model
  the HTTP route uses and calls the same underlying service function — **no
  CLI-specific business logic**, exactly like `llm-gateway-service`'s
  `express-cli-adapter`-style pattern (`sql-assessment-service` has an literal
  `express-cli-adapter.ts` doing this; Python equivalent is a shared
  `core/*` call invoked from both `api/routes/*.py` and `cli/commands/*.py`).
  Note: `express-cli-adapter.ts` was cited from `sql-assessment-service`, not
  `llm-gateway-service` — double check the CLI/route code-sharing pattern used there
  during implementation, since the two services may differ in how strictly they
  share the adapter layer between HTTP and CLI.
- Input/output is JSON on stdin/stdout/files, per the repo's established "JSON in,
  JSON out" CLI convention, so it can be invoked from workflow orchestrators
  identically to the TypeScript services' CLIs.
- Credentials passed via `--credentials` on the CLI are subject to the exact same
  Credential Resolver validation as the HTTP path (§7) — no separate/looser CLI
  credential handling.

---

## 5. Pagination Instead of Background Jobs

Per the confirmed decision, neither batch downloads nor multi-level citation graphs
use a server-tracked job store. Both are reshaped as **paginated, stateless,
cursor-driven** operations:

### 5.1 Batch downloads

`POST /v1/download` accepts a bounded batch (default/max `20` `paper_ids` per call,
configurable via `DOWNLOAD_MAX_BATCH_SIZE`). Requests exceeding the bound are
rejected with `400` and a message telling the caller to paginate their own
`paper_ids` list client-side across multiple calls — there is no `job_id`/polling
concept. Each call is fully synchronous and returns per-item status
(`ok`/`paywalled`/`not_found`/`error`) directly in the response body, same shape as
before but without the wrapping job envelope. This keeps the download path
stateless and infra-free (no queue, no persisted job table) while still bounding
per-request latency and backend load.

### 5.2 Citation graph expansion

`POST /v1/graph` performs **one BFS level per call**, not the full `max_depth`
expansion, and returns an opaque `cursor`:

```jsonc
// Request (first call — no cursor)
{
  "seeds": ["10.xxxx/yyyy"],
  "direction": "both",
  "max_depth": 2,
  "max_nodes_per_level": 100,
  "credentials": { "scopus": { "api_key": "…" } }
}
```

```jsonc
// Response
{
  "nodes": [ /* nodes discovered at this level */ ],
  "edges": [ /* edges discovered at this level */ ],
  "depth_reached": 1,
  "max_depth": 2,
  "done": false,
  "cursor": "opaque-base64-token"     // encodes: frontier node ids, visited set, depth, dedup state
}
```

The caller resubmits `{"cursor": "opaque-base64-token", "credentials": {...}}` to
fetch the next level, repeating until `done: true` (either `max_depth` reached or the
frontier is empty). `max_total_nodes` is still enforced across calls by encoding the
running total in the cursor.

- The cursor is a **self-contained, signed** (HMAC, using a service-side secret) blob
  — the service itself holds no per-graph state between calls, so this remains
  infra-free (no Redis, no in-memory dict, no job table) and horizontally scalable
  across replicas.
- Cursor payload size is bounded by `max_nodes_per_level`, so it stays well within
  typical header/body size limits even at `max_total_nodes` in the low thousands; if
  usage later needs much larger graphs, revisit with real persistence (§8 open
  questions) rather than growing the cursor unboundedly.
- The CLI's `graph` subcommand loops calling `/v1/graph` internally with the returned
  cursor until `done: true`, so CLI users get the equivalent of the old "one call,
  fully expanded" ergonomics for free, while the HTTP API stays paginated and
  stateless for programmatic/workflow callers who want incremental results.
- `unified-api-implementation-plan.md` §7 ("expose it as an async job… `202 { job_id
  }`… poll `/v1/jobs/{id}`") should be treated as **superseded** by this section for
  this repo; the response-shape example in that section (§7.2) still describes the
  *aggregate* result shape once a caller has looped to `done: true`, which remains
  useful as the CLI's final merged output shape.

---

## 6. CI Workflow

Add `.github/workflows/service-academic-search-service.yml`, following the
`fermentaladin-service` template exactly (Python job pattern: `setup-python` +
`astral-sh/setup-uv`), with the four staged jobs the other services use:

```yaml
name: academic-search-service

on:
  push:
    branches: ["master"]
    paths:
      - "services/academic-search-service/**"
  pull_request:
    branches: ["master"]
    paths:
      - "services/academic-search-service/**"

defaults:
  run:
    working-directory: services/academic-search-service

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: make lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: make test
      - uses: codecov/codecov-action@v4
        with:
          files: services/academic-search-service/coverage.xml
          flags: academic-search-service
          token: ${{ secrets.CODECOV_TOKEN }}
          fail_ci_if_error: false
        if: always()

  generate-openapi:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: make generate-openapi
      - uses: actions/upload-artifact@v4
        with:
          name: openapi-spec-academic-search-service
          path: services/academic-search-service/academic-search-service.openapi.json

  build:
    runs-on: ubuntu-latest
    needs: generate-openapi
    if: github.event_name == 'push' && github.ref == 'refs/heads/master'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/academic-search-service
          tags: |
            type=sha,prefix=sha-
            type=raw,value=latest
      - uses: docker/build-push-action@v6
        with:
          context: services/academic-search-service
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

No test-suite step should make live network calls to real academic APIs (rate limits,
flakiness, and credential requirements make that unsuitable for CI) — adapter tests
must run against recorded fixtures/mocked HTTP responses (`respx` for `httpx` mocking
is the natural choice given both backends are `httpx`-based).

---

## 7. Security, Credentials & Secrets

Adopt `llm-gateway-service`'s documented stance directly:

### 7.1 No built-in authentication (disclaimer, verbatim pattern)

The service README must carry the same class of disclaimer `llm-gateway-service`
carries: this service has **no built-in authentication/authorization** on any HTTP
endpoint. Securing it (private network segment, API gateway/reverse proxy with
auth, or an authenticating sidecar) is a **deployment-time obligation** of whoever
runs/embeds it — not something this service provides itself.

### 7.2 SSRF-safety on provider-returned URLs

Unlike `llm-gateway-service` (which validates a *caller-supplied* `customProvider`
URL), this service's outbound-request risk is different in shape but not in kind: it
fetches `pdf_url`/full-text URLs that come back **from third-party provider
responses** (§8 of the API plan, Download Service). Those provider responses are
themselves influenced by whatever a paper's metadata says, which is not fully
trusted input. Before this service issues any server-side fetch to a
provider-returned URL:

- Reuse the same category of check as `llm-gateway-service/src/core/url-safety.ts`
  (reject loopback, link-local, RFC1918 private ranges, and known cloud metadata
  endpoints) — port it to Python (`ipaddress` stdlib module) as
  `src/core/url_safety.py`, applied uniformly to every outbound fetch this service
  performs on a URL it did not itself construct from a trusted provider base-URL
  config value.
- This is best-effort (no DNS resolution before the check, same caveat
  `llm-gateway-service` documents) and does not replace network-level egress
  controls if this service is deployed somewhere those matter.

### 7.3 Credential handling

- Per-request `credentials.<provider>` blocks (HTTP body or `--credentials` CLI flag)
  are the primary path, exactly as designed in the API plan §5.1/§9.
- Service-level defaults (e.g. a shared `mailto` for OpenAlex/CrossRef's polite pool)
  come from environment variables, documented in the README's configuration table
  the same way `llm-gateway-service` documents `LLM_GATEWAY_API_KEY`. Naming
  convention: `<PROVIDER>_API_KEY` / `<PROVIDER>_MAILTO` (e.g. `SCOPUS_API_KEY`,
  `OPENALEX_MAILTO`, `IEEE_API_KEY`).
- Credentials are never logged (structured logger must redact any field named/nested
  under `credentials`/`api_key`/`token`), never written to disk, and never included
  in the `raw` field of a canonical `Paper` object even when `include_raw=true`.
- `.env.example` ships with placeholder values only (rename from
  `fermentaladin-service`'s `.demo.env` naming to the more conventional
  `.env.example`, since this service's credentials are more numerous and
  provider-specific than fermentaladin's — worth the naming deviation for clarity;
  flagged in §8 as a deliberate, minor deviation from precedent).

---

## 8. README, OpenAPI & Root Wiring

- `README.md` must contain, in this order (matching `llm-gateway-service`'s
  structure, which is the most complete precedent in the repo): a feature summary,
  a "Code Layout" tree, a configuration table (env vars, defaults, descriptions —
  every provider credential env var included), the security disclaimer (§7.1), an
  API endpoint table, and CLI usage examples.
- `src/generate_openapi.py` follows `fermentaladin-service/src/generate_openapi.py`'s
  pattern: import the FastAPI `app`, call `app.openapi()`, and write it to
  `academic-search-service.openapi.json` at the service root — committed to the repo
  like every other service's spec.
- Add a new row to the root `README.md` services table:

  ```markdown
  | [academic-search-service](services/academic-search-service/README.md) | Python | [![CI](...)](...) | [![codecov](...)](...) | Unified search/export/download/citation-graph API over academic-mcp and scimesh |
  ```

  and a matching CI badge in the badges block at the top of the root README, plus
  registering the workflow filename in that badge URL — follow the exact pattern the
  four existing badges use.

---

## 9. Open Questions / Deviations to Confirm Before Implementation

1. **`Typer` as a new dependency** — no Python service in the repo has a CLI yet, so
   there's no established precedent to match; confirm `Typer` (vs. plain `argparse`/
   `click`) is acceptable before adding it, since it's the one net-new tooling choice
   this plan introduces that isn't already used elsewhere in the repo.
2. **Port `8003`** — verify no other service has claimed it since this plan was
   written (`8000` fermentaladin, `8002` llm-gateway are the two Python/Node examples
   inspected; the other three TypeScript services weren't checked for their ports).
3. **`.env.example` vs `.demo.env` naming** — deliberately deviates from
   `fermentaladin-service`'s `.demo.env` precedent (§7.3); confirm this is acceptable
   or whether strict naming consistency with the one existing Python service is
   preferred over the more common `.env.example` convention.
4. **Cursor secret management** — the HMAC signing key for graph-pagination cursors
   (§5.2) needs an env var (`GRAPH_CURSOR_SECRET`) and a rotation story; not yet
   covered by any existing service's secret-management pattern in this repo since
   none of them sign anything today.
5. **`packages/python/` reuse** — both `packages/python/` and `packages/typescript/`
   are currently empty stubs (`.gitkeep` only). Nothing today justifies extracting
   shared code (e.g. the canonical `Paper` schema or export serializers) into
   `packages/python/` ahead of a second Python service actually needing it — revisit
   only if/when a second consumer appears, per the root README's stated
   "two or more services in the same language" threshold for creating a shared
   package.
