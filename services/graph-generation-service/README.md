# Graph Generation Service

FastAPI service for validated graph generation through NetworkX, python-igraph, and NetworKit adapters.

Requests use a two-level discriminated union: `algorithm` selects the graph family and `backend` selects the
backend-specific parameter schema. The discovery endpoint publishes the complete Spec A schema catalog.

The complete Spec A catalog is executable: 23 algorithm families and 42 backend combinations covering random,
degree-sequence, community, geometric, deterministic, tree, bipartite, fitness, attachment, R-MAT, and hyperbolic
generators. Backend-specific parameters are validated before execution, including each supported `variant`.

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

Supported exports are `edge_list`, `adjacency`, `graphml`, `gml`, and `graph6`. JSON formats are returned
directly; GraphML, GML, and graph6 are streamed with format-specific content types.

Generated graphs are currently retained in an in-memory resource store. Durable storage and asynchronous
generation for large graphs are not implemented yet.

## Architecture

The API layer does not import graph frameworks. Library-specific objects remain behind adapter boundaries and
are wrapped in a shared internal result containing the graph object, node count, edge count, and directedness.

## Docker

Build and run locally:

```sh
make docker-build
docker run --rm -p 8002:8002 graph-generation-service
```

## Development

```sh
make prep
make build
make lint
make test
make generate-openapi
make clean
```
