# Edit Distance Service

Unified REST API for text edit distance and graph edit distance (GED) algorithms, powered by 8 open-source libraries. Part of the ALADIN microservice ecosystem.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/text/algorithms` | List all text algorithms + available backends |
| `POST` | `/v1/text/distance` | Compute text edit distance (synchronous) |
| `GET` | `/v1/graphs/algorithms` | List all GED algorithms + available backends |
| `POST` | `/v1/graphs/distance` | Compute graph edit distance (synchronous) |

## Text Algorithms

| Algorithm | Default Backend | Result Type |
|-----------|----------------|--------------|
| `levenshtein` | rapidfuzz | scalar_distance |
| `damerau_levenshtein` | rapidfuzz | scalar_distance |
| `hamming` | rapidfuzz | scalar_distance |
| `jaro_winkler` | rapidfuzz | scalar_distance |
| `osa` | rapidfuzz | scalar_distance |
| `indel` | rapidfuzz | scalar_distance |
| `lcs` | textdistance | sequence |
| `needleman_wunsch` | textdistance | alignment |
| `gotoh` | textdistance | scalar_distance |
| `smith_waterman` | textdistance | scalar_distance |
| `token_set_similarity` | textdistance | scalar_distance |
| `ncd` | textdistance | scalar_distance |
| `phonetic_encoding` | jellyfish | phonetic_code |
| `long_sequence_alignment` | edlib | alignment |
| `diff_patch` | diff_match_patch | edit_script |

→ Each algorithm selects a default backend automatically. Use the `backend` field in the request to override (see the discovery endpoint for available combinations).

## Graph Algorithms

| Algorithm | Default Backend | Description |
|-----------|----------------|-------------|
| `ged_astar` | networkx | Exact GED (A\*), anytime approximation, edit path |
| `ged_heuristic` | gedlib | BIPARTITE, IPFP, REFINE, lower bounds |
| `ged_hausdorff` | gmatch4py | Hausdorff Edit Distance (cheap upper bound) |
| `ged_greedy` | gmatch4py | Greedy Edit Distance (fast approximation) |

## Examples

### Text Algorithms

#### Levenshtein (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "levenshtein",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Damerau-Levenshtein (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "damerau_levenshtein",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "jellyfish", "b": "jellyfihs"}
    ]
  }' | jq .
```

#### Hamming (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "hamming",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "karolin", "b": "kathrin"}
    ]
  }' | jq .
```

#### Jaro-Winkler (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "jaro_winkler",
    "params": {"variant": "jaro_winkler", "prefix_weight": 0.1},
    "inputs": [
      {"id": "p1", "a": "MARTHA", "b": "MARHTA"}
    ]
  }' | jq .
```

#### OSA — Optimal String Alignment (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "osa",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "ca", "b": "abc"}
    ]
  }' | jq .
```

#### Indel (RapidFuzz — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "indel",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### LCS — Longest Common Subsequence (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "lcs",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Needleman-Wunsch (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "needleman_wunsch",
    "params": {"gap_cost": 1.0},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Gotoh (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "gotoh",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Smith-Waterman (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "smith_waterman",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Token Set Similarity (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "token_set_similarity",
    "params": {"metric": "jaccard"},
    "inputs": [
      {"id": "p1", "a": "hello world", "b": "world hello"}
    ]
  }' | jq .
```

#### NCD — Normalized Compression Distance (textdistance — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ncd",
    "params": {"qval": 1, "compressor": "zlib"},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Phonetic Encoding (jellyfish — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "phonetic_encoding",
    "params": {"scheme": "soundex"},
    "inputs": [
      {"id": "w1", "text": "Jellyfish"},
      {"id": "w2", "text": "Jelyfsh"}
    ]
  }' | jq .
```

#### Long Sequence Alignment (edlib — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "long_sequence_alignment",
    "params": {"mode": "NW", "task": "distance"},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"}
    ]
  }' | jq .
```

#### Diff/Patch (diff-match-patch — default)
```bash
curl -s -X POST http://localhost:8000/v1/text/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "diff_patch",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "The quick brown fox", "b": "The slow brown fox"}
    ]
  }' | jq .
```

---

### Graph Algorithms

#### GED A* — NetworkX (default, exact mode)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "exact", "timeout_ms": 5000},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        },
        "g2": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}, {"source": "A", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

#### GED A* — NetworkX (anytime mode)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "anytime", "timeout_ms": 3000},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "1", "label": "A"}, {"id": "2", "label": "B"}],
          "edges": [{"source": "1", "target": "2"}]
        },
        "g2": {
          "nodes": [{"id": "1", "label": "A"}, {"id": "2", "label": "B"}, {"id": "3", "label": "C"}],
          "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
        }
      }
    ]
  }' | jq .
```

#### GED A* — NetworkX (edit path mode)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "path", "timeout_ms": 5000},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
          "edges": [{"source": "A", "target": "B"}]
        },
        "g2": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

#### GED Heuristic — GEDLIB (default, BIPARTITE method)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_heuristic",
    "params": {"method": "BIPARTITE"},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        },
        "g2": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}, {"source": "A", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

#### GED Hausdorff — GMatch4py (default)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_hausdorff",
    "params": {"node_del": 1.0, "node_ins": 1.0, "edge_del": 1.0, "edge_ins": 1.0},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
          "edges": [{"source": "A", "target": "B"}]
        },
        "g2": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

#### GED Greedy — GMatch4py (default)
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_greedy",
    "params": {"node_del": 1.0, "node_ins": 1.0, "edge_del": 1.0, "edge_ins": 1.0},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
          "edges": [{"source": "A", "target": "B"}]
        },
        "g2": {
          "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

#### GED A* — adjacency matrix format
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "exact", "timeout_ms": 5000},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "format": "adjacency_matrix",
          "matrix": [[0, 1, 1], [1, 0, 1], [1, 1, 0]],
          "node_labels": ["A", "B", "C"]
        },
        "g2": {
          "format": "adjacency_matrix",
          "matrix": [[0, 1], [1, 0]],
          "node_labels": ["A", "B"]
        }
      }
    ]
  }' | jq .
```

#### GED A* — networkx node-link format
```bash
curl -s -X POST http://localhost:8000/v1/graphs/distance \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "exact", "timeout_ms": 5000},
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "format": "node_link",
          "nodes": [{"id": "A", "attr": "red"}, {"id": "B", "attr": "blue"}],
          "links": [{"source": "A", "target": "B", "weight": 1}]
        },
        "g2": {
          "format": "node_link",
          "nodes": [{"id": "A", "attr": "red"}, {"id": "B", "attr": "green"}, {"id": "C", "attr": "blue"}],
          "links": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        }
      }
    ]
  }' | jq .
```

> **Batching:** Both endpoints accept arrays — multiple pairs per request are supported.
> **Custom backends:** Override the default backend by adding `"backend": "<name>"` to the request body. Use `GET /v1/text/algorithms` or `GET /v1/graphs/algorithms` to discover all available algorithm/backend combinations.

## Input Formats

### Text (inputs array)

Each element is either a **pair** or a **phonetic encoding** request:

| Type | Fields |
|------|--------|
| `InputPair` | `id`, `a` (first string), `b` (second string) |
| `InputPhonetic` | `id`, `text` (single word) |

The service distinguishes them automatically — phonetic algorithms expect `InputPhonetic`, all others expect `InputPair`.

### Graph (graphs array)

Each element is a `GraphPair` with `id`, `g1`, `g2`.  
Three input formats are supported, selected via the optional `format` field:

#### Default — nodes + edges (explicit)

```json
{
  "g1": {
    "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
    "edges": [{"source": "A", "target": "B"}]
  }
}
```

Node attrs beyond `id` become vertex labels. Edge attrs beyond source/target become edge labels.

#### `"format": "node_link"` — networkx JSON

Same structure as the [networkx node-link format](https://networkx.org/documentation/stable/reference/readwrite/json_graph.html), using `links` instead of `edges`:

```json
{
  "format": "node_link",
  "nodes": [{"id": "A", "label": "cat"}, {"id": "B", "label": "dog"}],
  "links": [{"source": "A", "target": "B", "weight": 1.0}],
  "directed": false
}
```

#### `"format": "adjacency_matrix"` — dense matrix

```json
{
  "format": "adjacency_matrix",
  "matrix": [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
  "node_labels": ["A", "B", "C"]
}
```

Omitting `node_labels` auto-generates `["0", "1", …]`. Only the upper triangle is used (undirected). Zero entries → no edge.

## Result Types

| result_type | Contains | Example Algorithms |
|-------------|----------|-------------------|
| `scalar_distance` | value, normalized | levenshtein, hamming, jaro_winkler |
| `sequence` | value, length | lcs |
| `alignment` | edit_distance, locations, cigar | needleman_wunsch, long_sequence_alignment |
| `edit_script` | diffs, levenshtein | diff_patch |
| `phonetic_code` | codes (dict) | phonetic_encoding |

## Quick Start

```bash
cd services/edit-distance-service
python3.12 -m venv .venv && source .venv/bin/activate
make prep              # pip install -e ".[dev,graph]"
make test              # pytest -v
make start             # uvicorn src.main:app --reload (port 8000)
```

## Docker

```bash
make dev   # docker-compose -f docker-compose.dev.yml up --build
make prod  # docker-compose -f docker-compose.prod.yml up --build
```

## Project Structure

```
services/edit-distance-service/
├── pyproject.toml          # Dependencies (rapidfuzz, textdistance, jellyfish, edlib,
│                           #   diff-match-patch, networkx, gedlibpy, gmatch4py)
├── Dockerfile              # Multi-stage build
├── Makefile                # prep, build, test, lint, start, docker-build, …
├── src/
│   ├── main.py             # FastAPI app (REST endpoints)
│   ├── models.py           # Pydantic models (request/response)
│   ├── cli.py              # Click CLI (list, compare, health, ged, batch)
│   ├── text/__init__.py    # Text ED implementations + dispatcher
│   └── graph/__init__.py   # Graph ED implementations + dispatcher
├── tests/
│   ├── test_text_compare.py    # Unit tests (all 15 algorithms)
│   ├── test_graph_compare.py   # Unit tests (all 4 GED algorithms)
│   ├── test_integration.py     # HTTP integration tests
│   └── test_smoke.sh           # Bash smoke test
└── http-tests/
    ├── health.http             # VS Code REST Client examples
    ├── text_algorithms.http
    └── graph_algorithms.http
```

## CLI

The service ships with a Click-based CLI (`edit-distance`) that mirrors every REST endpoint.

```bash
# Install with CLI dependencies
pip install -e ".[dev]"

# Start the service (in another terminal)
make start

# Health check
edit-distance health

# List algorithms
edit-distance list-text
edit-distance list-graphs

# Compute Levenshtein distance (default example)
edit-distance text-distance levenshtein

# Compute with explicit inputs
edit-distance text-distance levenshtein \
  -i '{"id":"p1","a":"kitten","b":"sitting"}' \
  -i '{"id":"p2","a":"kitten","b":"kittens"}'

# Compute from a JSON file
edit-distance text-distance levenshtein -f inputs.json

# Override backend and pass parameters (shorthand: true/false/null + numbers)
edit-distance text-distance levenshtein --backend jellyfish -p score_cutoff=5

# Complex params via JSON (arrays, objects, booleans)
edit-distance text-distance levenshtein -p '{"weights": [1, 1, 1], "processor": null}'

# GED example (shorthand)
edit-distance ged-distance ged_astar -p mode=exact -p timeout_ms=5000

# GED example (full JSON)  
edit-distance ged-distance ged_astar -p '{"mode":"exact","timeout_ms":5000}'

# Point at a different host
edit-distance --base http://my-host:8000 health
```

Set `EDIT_DISTANCE_BASE_URL` to avoid repeating `--base`.

| Command | Description |
|---------|-------------|
| `edit-distance health` | Check service health |
| `edit-distance list-text` | List text algorithm/backend combinations |
| `edit-distance list-graphs` | List GED algorithm/backend combinations |
| `edit-distance text-distance <algo>` | Compute text edit distance |
| `edit-distance ged-distance <algo>` | Compute graph edit distance |

## Make Commands

| Command | Action |
|---------|--------|
| `make prep` | Install dev dependencies |
| `make test` | Run tests (pytest -v) |
| `make lint` | Lint + format check (ruff) |
| `make start` | Start dev server (hot-reload) |
| `make docker-build` | Build Docker image |
| `make generate-openapi` | Generate OpenAPI spec |
| `make dev` / `make prod` | Docker Compose (dev/prod) |
