# Edit Distance Service

Unified REST API for text edit distance and graph edit distance (GED) algorithms, powered by 8 open-source libraries. Part of the ALADIN microservice ecosystem.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/text/algorithms` | List all text algorithms + available backends |
| `POST` | `/v1/text/compare` | Compute text edit distance (synchronous) |
| `GET` | `/v1/graphs/ged/algorithms` | List all GED algorithms + available backends |
| `POST` | `/v1/graphs/ged/compute` | Compute graph edit distance (synchronous) |

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

## Quick Examples

### Levenshtein (Text)
```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "levenshtein",
    "params": {},
    "inputs": [{"id": "p1", "a": "kitten", "b": "sitting"}]
  }'
```

### GED A\* (Graph)
```bash
curl -X POST http://localhost:8000/v1/graphs/ged/compute \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "params": {"mode": "exact", "timeout_ms": 5000},
    "graphs": [{
      "id": "pair-1",
      "g1": {"nodes": [{"id":"A"},{"id":"B"}], "edges": [{"source":"A","target":"B"}]},
      "g2": {"nodes": [{"id":"A"},{"id":"B"},{"id":"C"}], "edges": [{"source":"A","target":"B"},{"source":"B","target":"C"}]}
    }]
  }'
```

> Batching: Both endpoints accept arrays — multiple pairs per request are supported.

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
│   ├── cli.py              # Click CLI (list, compare, health, ged-compare)
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
