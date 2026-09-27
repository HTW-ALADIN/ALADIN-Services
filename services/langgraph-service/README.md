# langgraph-service

Generic LangGraph execution engine over caller-supplied graph definitions (no prebuilt workflows).

- Callers POST a JSON graph definition (`llm`, `http`, `transform`, `conditional` nodes), create a thread, then invoke runs synchronously or stream them as SSE.
- All `llm` steps route through the existing `llm-gateway-service` (`POST /generate` with the `openai-chat` wire shape), keeping model credentials/routing centralized there.
- Checkpointing is pluggable: `InMemorySaver` by default (no infra), `AsyncPostgresSaver` opt-in via env + compose profile.
- HTTP API (FastAPI) and CLI (Typer), sharing the same `core/*` logic.

Graph definitions are data only: a closed node set with `$.path` lookups, no `eval`/`exec`, no expression language. Definitions and thread metadata are ephemeral in v1 — re-POST them after a restart.

## Code Layout

```text
src/main.py                     FastAPI app (lifespan: checkpointer + run limiter)
src/config.py                   Env-driven configuration (gateway, checkpointer, limits)
src/generate_openapi.py         Writes langgraph-service.openapi.json
src/api/routes/                 HTTP routes (health, graphs, threads, runs)
src/core/dsl.py                 JSON DSL validation (closed node set, topology checks)
src/core/compiler.py            DSL -> StateGraph compilation (wrapped `data` channel)
src/core/runner.py              Sync invoke + SSE streaming orchestration
src/core/nodes/llm.py           Gateway-backed LLM node (POST /generate)
src/core/nodes/http_tool.py     Generic HTTP tool node (for sibling ALADIN services)
src/core/nodes/transform.py     Pure data ops (pick/merge/const)
src/core/nodes/template.py      `$.path` template rendering (no expressions)
src/core/url_safety.py          SSRF-safety checks for caller-supplied URLs
src/core/store.py               Ephemeral graph/thread registries
src/core/checkpointer.py        InMemorySaver vs AsyncPostgresSaver factory
src/core/limits.py              Run concurrency semaphore + wall deadlines
src/core/errors.py              Domain errors mapped to HTTP status codes
src/cli/                        Typer CLI mirroring the HTTP API 1:1
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | HTTP host to bind |
| `PORT` | `8004` | HTTP port used by `make start` and the Docker container |
| `LOG_LEVEL` | `info` | Log verbosity |
| `LLM_GATEWAY_BASE_URL` | `http://localhost:8002` | Base URL of `llm-gateway-service` (unprefixed routes: `POST {base}/generate`) |
| `LLM_GATEWAY_API_KEY` | unset | Bearer token for gateway-routed `llm` nodes; missing → `llm` nodes fail fast, `/health` still OK |
| `LLM_NODE_TIMEOUT_SECONDS` | `60` | Per-`llm`-node timeout |
| `LLM_RETRY_ONCE` | `false` | Retry gateway calls once on 502/503/504 |
| `HTTP_NODE_TIMEOUT_SECONDS` | `30` | Per-`http`-node timeout |
| `MAX_TOOL_RESPONSE_BYTES` | `1048576` | `http`-node response body cap |
| `LANGGRAPH_CHECKPOINTER` | `memory` | `memory` \| `postgres` |
| `POSTGRES_URL` | unset | Required when `LANGGRAPH_CHECKPOINTER=postgres` |
| `RUN_TIMEOUT_SECONDS` | `120` | Per-run wall deadline (`504` on expiry) |
| `RUN_CONCURRENCY` | `4` | Concurrent runs per process; excess → `503` without queueing |
| `RECURSION_LIMIT` | `25` | LangGraph recursion cap per run |
| `MAX_GRAPH_BYTES` | `65536` | Graph definition size cap (`413` on excess) |
| `MAX_INPUT_BYTES` | `262144` | Run input size cap (`413` on excess) |
| `MAX_OUTPUT_BYTES` | `1048576` | Run output/event size cap (`502` on excess) |

No LLM provider keys live here — only the gateway connection details above.

## Security Disclaimer: authentication is NOT provided by this service

**This service has no built-in authentication or authorization on any of its HTTP endpoints** (`/v1/graphs`, `/v1/threads`, `/v1/threads/*/runs`, `/v1/threads/*/runs:stream`). Anyone who can reach the service over the network can invoke it, including defining graphs that make the service issue outbound HTTP requests (to `llm-gateway-service` and to caller-supplied `http`-node URLs).

**Securing access to this service is a deployment-time obligation delegated to whoever runs/embeds it** — the consuming system, workflow orchestrator, or platform team deploying this service is responsible for placing it behind an appropriate auth boundary before it is reachable from anything other than a fully trusted network. Suitable options include (non-exhaustive):

- Only binding/exposing the service on a private network segment reachable exclusively by the trusted workflow system that calls it.
- Fronting it with an API gateway, reverse proxy, or service mesh that enforces authentication (API keys, mTLS, OAuth2/OIDC, network policies) before requests reach this service.
- Wrapping it in an authenticating sidecar/proxy if the deployment platform does not offer the above natively.

Related mitigations exist in the service itself, but none is a substitute for an auth boundary:

- Every caller-supplied `http`-node URL is checked by `src/core/url_safety.py` (rejects non-http(s) schemes, loopback, link-local, RFC1918 private ranges, and known cloud metadata endpoints) before any request is made. This is a best-effort, static hostname/IP-literal check — it does not resolve DNS, and does not prevent requests to arbitrary **public** URLs.
- Caller-supplied `Authorization`/`Cookie` headers are rejected on `http` nodes (only `Content-Type: application/json` is allowed), and the gateway API key always comes from service env, never from graph definitions.
- Graph definitions are data only: no `eval`/`exec`, no expression language — only `$.dotted.path` lookups with integer list indexes. `transform` ops are limited to `pick`/`const`/`merge`; `conditional` routing is limited to `when-equals` cases plus a default.
- Secrets are never logged, never persisted to disk, and never echoed in thread state/history.
- Resource bounds (node/edge counts, request-byte caps, run timeout, concurrency semaphore with fast `503`) mirror `graph-generation-service` admission control.

**Do not expose this service on an untrusted network without first adding an authentication layer in front of it.**

## API

Start the service:

```sh
make start
```

The API listens on port `8004` by default. OpenAPI docs: `http://localhost:8004/docs`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `GET` | `/readyz` | Readiness incl. checkpointer health (+ gateway probe when a key is configured) |
| `POST` | `/v1/graphs` | Validate a DSL definition and store it → `graph_id` |
| `GET` | `/v1/graphs` | List stored graph ids/names |
| `GET` | `/v1/graphs/{graphId}` | Fetch a stored definition |
| `DELETE` | `/v1/graphs/{graphId}` | Delete a definition (`204`) |
| `POST` | `/v1/threads` | Create a thread for a graph → `thread_id` |
| `GET` | `/v1/threads/{threadId}/state` | Latest checkpoint state |
| `GET` | `/v1/threads/{threadId}/history` | Checkpoint history (`?limit=`, max 100) |
| `DELETE` | `/v1/threads/{threadId}` | Delete a thread (`204`) |
| `POST` | `/v1/threads/{threadId}/runs` | Synchronous invoke `{input}` → `{output}` |
| `POST` | `/v1/threads/{threadId}/runs:stream` | SSE stream of per-node updates |

### Graph definition DSL

A definition wires a closed node set. `llm` nodes send `openai-chat`-shaped `POST /generate` requests to the gateway; `http` nodes call sibling ALADIN services; `transform` reshapes state; `conditional` nodes only route (wired via `conditional_edges`).

```json
{
  "name": "search-then-summarize",
  "nodes": [
    {
      "id": "search",
      "type": "http",
      "url": "http://academic-search-service:8003/v1/search",
      "method": "POST",
      "body_template": {"query": "$.query"},
      "output_key": "papers"
    },
    {
      "id": "summarize",
      "type": "llm",
      "provider": "openai",
      "model": "gpt-4o",
      "system": "Summarize the papers in one sentence.",
      "input_key": "papers",
      "output_key": "summary"
    }
  ],
  "edges": [["search", "summarize"]],
  "entry": "search"
}
```

End-to-end example (transform-only, no gateway key needed):

```sh
curl -X POST http://localhost:8004/v1/graphs -H 'Content-Type: application/json' -d '{
  "name": "echo",
  "nodes": [
    {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]}
  ],
  "edges": [],
  "entry": "a"
}'
# {"graph_id": "gr_...", "name": "echo", ...}

curl -X POST http://localhost:8004/v1/threads -H 'Content-Type: application/json' \
  -d '{"graph_id": "gr_..."}'
# {"thread_id": "th_...", ...}

curl -X POST http://localhost:8004/v1/threads/th_.../runs -H 'Content-Type: application/json' \
  -d '{"input": {"start": true}}'
# {"output": {"start": true, "value": 1}}
```

## CLI

```sh
uv run langgraph-service graph create --file graph.json
uv run langgraph-service graph get <graph_id>
uv run langgraph-service graph list
uv run langgraph-service graph delete <graph_id>

uv run langgraph-service thread create --graph <graph_id>
uv run langgraph-service thread state <thread_id>
uv run langgraph-service thread history <thread_id> --limit 20
uv run langgraph-service thread delete <thread_id>

uv run langgraph-service run invoke <thread_id> --input '{"query": "..."}'
uv run langgraph-service run stream <thread_id> --input '{"query": "..."}'
```

The CLI's `run stream` prints one JSON object per node update; the HTTP API streams SSE frames instead. `make cli ARGS="..."` forwards to the same entrypoint.

## Docker

Build:

```sh
make docker-build
```

Run the HTTP API standalone (in-memory checkpointer, no database):

```sh
docker run --rm -p 8004:8004 \
  -e LLM_GATEWAY_BASE_URL=http://gateway:8002 \
  -e LLM_GATEWAY_API_KEY \
  langgraph-service
```

Run with durable Postgres threads:

```sh
LANGGRAPH_CHECKPOINTER=postgres \
POSTGRES_URL=postgresql://langgraph:langgraph@postgres:5432/langgraph \
docker compose --profile postgres up --build
```

The `postgres` service is profile-gated: without `--profile postgres` the app container runs alone with the in-memory checkpointer.

## Development

```sh
make prep
make lint
make test
make generate-openapi
```

Tests mock the gateway (`respx`) and the checkpointer (in-memory) — no live network or database in CI. Postgres mode is covered by constructor/selection unit tests; exercise it locally via the compose profile above.
