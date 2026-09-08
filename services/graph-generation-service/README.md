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
      "n": 1000,
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

Supported exports are `edge_list`, `adjacency`, `graphml`, `gml`, and `graph6`. JSON formats are returned
directly; GraphML, GML, and graph6 are streamed with format-specific content types.

The CLI runs the same validation, adapter routing, and export logic without starting the API:

```sh
graph-generation-service generate request.json
cat request.json | graph-generation-service generate -
```

Requests are limited to 10,000 generated nodes. Up to 100 graphs are retained in memory, with the oldest resource
evicted when the limit is reached. Durable storage and asynchronous generation are not implemented yet.

## Architecture

The API layer does not import graph frameworks. Library-specific objects remain behind adapter boundaries and
are wrapped in a shared internal result containing the graph object, node count, edge count, and directedness.

graph-tool is intentionally excluded from the primary image because its native dependency stack is materially
larger than the Tier 1 libraries. Requests with `backend: graph_tool` are sent to the private sidecar over its
internal `/v1/generate` endpoint. The sidecar returns only normalized nodes, edges, and directedness; the primary
service continues to own resource IDs, storage, exports, public errors, OpenAPI, and CLI behavior. The sidecar port
is not published by the Compose deployment.

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

The primary service is suitable for a baseline allocation of 1 vCPU and 512 MiB RAM. The graph-tool sidecar should
start with 2 vCPU and 2 GiB RAM because graph-tool, NumPy, Boost, and OpenMP have a larger resident footprint and
spatial generators can allocate working sets proportional to the graph and point dimensions. A complete Tier 2 pod
should therefore start at 2 vCPU and 2.5 GiB RAM. These are deployment baselines rather than hard limits; benchmark
the intended algorithm mix and concurrency before production sizing.

`GRAPH_TOOL_SIDECAR_TIMEOUT_SECONDS` controls the primary-to-sidecar timeout and defaults to 30 seconds.
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
