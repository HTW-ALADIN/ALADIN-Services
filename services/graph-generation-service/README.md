# Graph Generation Service

FastAPI service for validated graph generation through NetworkX, python-igraph, NetworKit, and an isolated
graph-tool sidecar.

Requests use a two-level discriminated union: `algorithm` selects the graph family and `backend` selects the
backend-specific parameter schema. The discovery endpoint publishes the complete Spec B schema catalog.

This is the full-coverage Tier 2 design from the project research. The catalog is executable: 26 algorithm tags
and 46 native backend combinations covering random,
degree-sequence, community, geometric, deterministic, tree, bipartite, fitness, attachment, R-MAT, and hyperbolic
generators. Backend-specific parameters are validated before execution, including each supported `variant`.

Tier 2 is a backward-compatible extension of Tier 1. It retains all NetworkX, igraph, and NetworKit operations and
adds graph-tool for the three previously uncovered families plus two generalized alternatives:

| Algorithm | graph-tool operation | Purpose |
| --- | --- | --- |
| `knn_graph` | `generate_knn(points, k, ...)` | k-nearest-neighbor graph from explicit or generated points |
| `triangulation` | `triangulation(points, type, periodic)` | 2D or 3D simple or Delaunay triangulation |
| `price_network` | `price_network(N, m, c, gamma, directed)` | directed Price or undirected preferential-attachment model |
| `configuration_model` | `random_graph(N, deg_sampler, ...)` | generalized directed or undirected degree-sequence model |
| `stochastic_block_model` | `generate_sbm(...)` or `generate_maxent_sbm(...)` | Poisson, degree-corrected, microcanonical, or max-entropy SBM |

## API

Start the service:

```sh
make start
```

The API listens on port `8002` by default. OpenAPI documentation is available at
`http://localhost:8002/docs`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/algorithms` | List algorithm/backend combinations and parameter schemas |
| `POST` | `/v1/graphs` | Validate a request and generate a graph resource |
| `GET` | `/v1/graphs/{graphId}` | Retrieve graph resource metadata |
| `GET` | `/v1/graphs/{graphId}?format=<format>` | Export a generated graph |
| `DELETE` | `/v1/graphs/{graphId}` | Release a generated graph resource |

Example request:

```json
{
  "algorithm": "barabasi_albert",
  "backend": "networkx",
  "params": {
    "n": 500,
    "m": 3,
    "seed": 42
  },
  "output": {
    "format": "edge_list",
    "directed": false,
    "labels": "index"
  }
}
```

Tier 2 graph-tool example:

```json
{
  "algorithm": "knn_graph",
  "backend": "graph_tool",
  "params": {
    "pointGenerator": {
      "n": 500,
      "dimensions": 3,
      "seed": 42
    },
    "k": 8,
    "exact": false
  },
  "output": {
    "format": "edge_list",
    "directed": false,
    "labels": "index"
  }
}
```

Supported exports are `edge_list`, `adjacency`, `graphml`, `gml`, and `graph6`, returned with format-specific
content types. GraphML and GML preserve parallel edges; graph6 rejects parallel edges and self-loops.
Serialization runs in a bounded worker and completes before the response is sent.

The CLI runs the same validation, adapter routing, and export logic without starting the API:

```sh
graph-generation-service generate request.json
cat request.json | graph-generation-service generate -
```

Requests are limited by node count, estimated edges and estimated work before generation, and by actual node and
edge counts afterward. Up to 100 graphs are retained under an additional estimated memory budget, with the oldest
resource evicted when either budget is reached. An entry larger than the entire budget is rejected without
evicting existing entries. Durable storage and asynchronous generation are not implemented yet.

## Architecture

Each Tier 1 generation job and each export runs in a fresh Python worker process. The parent receives a bounded
normalized result. Workers are killed and reaped at their deadline; native aborts and memory failures do not run
inside the API process. There is a fixed worker capacity and no unbounded job queue. Fresh processes add startup
latency, but also prevent one job's native library state from affecting another job.

graph-tool is intentionally excluded from the primary image because its native dependency stack is materially
larger than the Tier 1 libraries. Requests with `backend: graph_tool` are sent to the private sidecar over its
internal `/v1/generate` endpoint. The sidecar returns only normalized nodes, edges, and directedness; the primary
service continues to own resource IDs, storage, exports, public errors, OpenAPI, and CLI behavior. The sidecar port
is not published by the Compose deployment.
The sidecar independently validates requests using the same schemas and budgets, and runs each generation in its
own bounded worker. Its CPU and wall deadlines remain active even if the primary disconnects or its HTTP timeout
expires. A disconnected caller does not immediately cancel remote work; it can continue only until the sidecar's
own deadline. Keep limits consistent across both services.

The primary service exposes `/healthz` for liveness and `/readyz` for readiness. Readiness includes the graph-tool
sidecar so a Tier 2 deployment does not report ready while graph-tool requests would fail. These operational routes
are intentionally excluded from the public Spec B OpenAPI surface, whose graph endpoints remain backward compatible.

NetworKit is pinned to 11.2 because it is the latest release that publishes both Linux AMD64 and Linux ARM64 wheels.
NetworKit 11.2.1 removed Linux ARM64 wheels, and its source distribution does not build reliably on that platform.

## Docker

Build both images and run the full Tier 2 deployment:

```sh
make docker-build
docker compose up --build
```

The primary image can still run by itself for Tier 1 backends:

```sh
docker run --rm -p 8002:8002 graph-generation-service
```

When using the host-installed CLI with graph-tool, point it at a running sidecar:

```sh
GRAPH_TOOL_SIDECAR_URL=http://localhost:8003 graph-generation-service generate request.json
```

## Resource requirements

Compose limits the primary container to 2 GiB RAM and the sidecar to 3 GiB, with 2 CPUs and 128 processes/threads
per container. Each container runs one job at a time. Allocate room for those 5 GiB combined ceilings and benchmark
the intended workload; these are safety ceilings, not measured minimum hardware requirements.

Workers enforce a 2 GiB virtual address-space limit on Linux, a CPU deadline, and a result-file limit before
importing native libraries. On macOS the address-space limit is not applied; use the Linux Docker deployment for
memory containment. Native OpenMP/BLAS worker threads are limited to one. Running multiple API server workers
multiplies worker capacity and in-memory stores; the supplied deployment uses one server process per container.

All limits below are positive integers, read at process startup. Restart the services after changes. No zero or
unlimited setting is accepted. The CLI and API share these controls.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `GRAPH_NODES` | 10000 | Maximum generated nodes |
| `GRAPH_EDGES` | 100000 | Maximum estimated and actual edges |
| `GRAPH_WORK` | 2000000 | Maximum estimated work units; not a precise runtime prediction |
| `GRAPH_REQUEST_BYTES` | 1048576 | Input body/file/stdin bytes, before JSON decoding |
| `GRAPH_RESULT_BYTES` | 16777216 | Worker result and sidecar response bytes |
| `GRAPH_EXPORT_BYTES` | 8388608 | Serialized export bytes |
| `GRAPH_STORED_BYTES` | 134217728 | Estimated retained graph memory |
| `GRAPH_STORED_GRAPHS` | 100 | Retained graph count |
| `GRAPH_SECONDS` | 20 | Wall and CPU deadline per generation/export job |
| `GRAPH_MEMORY_BYTES` | 2147483648 | Linux worker virtual address space |
| `GRAPH_CONCURRENCY` | 2 | Concurrent jobs per server process; Compose sets 1 |

HTTP request admission is capped at twice the worker capacity before reading request bodies; excess requests
receive 503 without queueing. Liveness and readiness remain available during saturation.

Admission estimates intentionally err on the side of rejection: where no tighter bound is available, they use a
dense graph bound, even for a low-probability random graph. Coordinate/tuple dimensions are capped at 64.
Degree totals, edge factors, retries, and point dimensions contribute to the budgets. Runtime and memory limits
remain the final containment boundary for algorithms whose internal complexity cannot be predicted exactly.

The store accounts for 1 KiB per node, 2 KiB per edge, eight times serialized metadata bytes, and a 4 KiB entry
overhead. This is a conservative estimate, not an exact RSS measurement. Admission and FIFO eviction are atomic.
Container memory limits also bound temporary copies and requests still holding references to evicted graphs.

Algorithm-specific validation and the 2,000,000 expected-edge ceiling return `400`.
Additional safety-budget failures, oversized bodies, stored entries and exports return `413 application/problem+json`; invalid
parameters return 400, worker saturation or abnormal termination returns 503, and wall deadlines return 504.
The CLI reports a JSON error on stderr and exits 2. Node-count validation keeps the existing 400 contract.

`GRAPH_TOOL_SIDECAR_TIMEOUT_SECONDS` controls the primary-to-sidecar transport timeout and defaults to
`GRAPH_SECONDS + 10` (30 seconds). Keep it longer than the sidecar worker deadline to receive the structured
deadline error. It is separate from the hard worker deadline.
`GRAPH_TOOL_SIDECAR_URL` defaults to `http://graph-tool-sidecar:8003`.

## Dependency and licensing notes

The sidecar installs Debian Trixie's `python3-graph-tool` package (`2.91+ds-5`) rather than compiling graph-tool in
the primary image. graph-tool is licensed under LGPL 3.0 or later. The Debian package keeps its copyright and license
files under `/usr/share/doc/python3-graph-tool/`; image distributors must preserve those notices and comply with the
applicable library licenses. See the [graph-tool license declaration](https://graph-tool.skewed.de/static/docs/stable/_modules/graph_tool.html)
and [Debian package metadata](https://packages.debian.org/trixie/python/python3-graph-tool).

## Development

```sh
make prep
make build
make lint
make test
make generate-openapi
make clean
```
