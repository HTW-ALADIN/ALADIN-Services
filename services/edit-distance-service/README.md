# Edit Distance Service

Unified microservice for text edit distance and graph edit distance (GED) algorithms, following the same architecture as the `noise-generation-service`.

## Library Selection

### Text Edit Distance (15 algorithm families)

| Libraries | Coverage |
|-----------|----------|
| **RapidFuzz** + **textdistance** + **jellyfish** | **13/15 (87%)** |
| + **edlib** + **diff-match-patch** | **15/15 (100%)** |

### Graph Edit Distance (10 algorithm families)

| Libraries | Coverage |
|-----------|----------|
| **NetworkX** + **GEDLIB** (via gedlibpy) | **8/10 (80%)** |
| + **GMatch4py** | **10/10 (100%)** |

## API Endpoints

### Part A — Text Edit Distance

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/text/algorithms` | Discovery: list all algorithm/backend combinations |
| `POST` | `/v1/text/compare` | Compute distance/similarity/transform (synchronous) |

### Part B — Graph Edit Distance

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/graphs/ged/algorithms` | Discovery: list all GED combinations |
| `POST` | `/v1/graphs/ged/compute` | Compute GED (synchronous, returns 201 with result inline) |

## Input Data Formats

### Text ED — `POST /v1/text/compare`

The `inputs` field accepts an array. You may provide either a single pair or multiple pairs in one request (batching).

#### Simple strings (default)

```json
{
  "algorithm": "levenshtein",
  "backend": "rapidfuzz",
  "params": {},
  "inputs": [
    { "id": "pair-1", "a": "kitten", "b": "sitting" }
  ]
}
```

| Field | Type | Description |
|------|-----|-------------|
| `id` | string | Arbitrary ID to identify the pair in the response |
| `a` | string | First text |
| `b` | string | Second text |

#### Phonetic encoding (different format)

For `algorithm: "phonetic_encoding"` each input object has only a single `text` field (not a pair, since individual words are encoded):

```json
{
  "algorithm": "phonetic_encoding",
  "backend": "jellyfish",
  "params": { "scheme": "soundex" },
  "inputs": [
    { "id": "w1", "text": "Jellyfish" },
    { "id": "w2", "text": "Robert" }
  ]
}
```

| Field | Type | Description |
|------|-----|-------------|
| `id` | string | Arbitrary ID |
| `text` | string | A single text to be phonetically encoded |

#### Batch processing

You can process any number of pairs in a single request — the service computes all entries in the same run:

```json
{
  "algorithm": "levenshtein",
  "backend": "rapidfuzz",
  "params": {},
  "inputs": [
    { "id": "p1", "a": "kitten", "b": "sitting" },
    { "id": "p2", "a": "flaw",   "b": "lawn" },
    { "id": "p3", "a": "Hello",  "b": "World" }
  ]
}
```

### Graph ED — `POST /v1/graphs/ged/compute`

The `graphs` field accepts an array of graph pairs. Each graph can be provided inline (with `nodes`/`edges`) or by reference (with `graphRef`).

#### Inline graphs (JSON structure)

```json
{
  "algorithm": "ged_astar",
  "backend": "networkx",
  "params": { "mode": "exact", "timeout_ms": 5000 },
  "graphs": [
    {
      "id": "pair-1",
      "g1": {
        "nodes": [
          { "id": "A", "label": "Person" },
          { "id": "B", "label": "Person" }
        ],
        "edges": [
          { "source": "A", "target": "B", "weight": 1.0 }
        ]
      },
      "g2": {
        "nodes": [
          { "id": "X", "label": "Person" },
          { "id": "Y", "label": "Person" }
        ],
        "edges": [
          { "source": "X", "target": "Y", "weight": 1.0 }
        ]
      }
    }
  ]
}
```

Node format:

| Field | Type | Description |
|------|-----|-------------|
| `id` | string | Required. Unique node ID within the graph |
| `label` | string (optional) | Node label (used for edit-cost comparisons) |
| `...` | any | Any additional attributes |

Edge format:

| Field | Type | Description |
|------|-----|-------------|
| `source` | string | Required. Source node ID |
| `target` | string | Required. Target node ID |
| `weight` | number (optional) | Edge weight |
| `label` | string (optional) | Edge label |
| `...` | any | Any additional attributes |

#### Graph by reference (for service composition)

```json
{
  "algorithm": "ged_astar",
  "backend": "networkx",
  "params": { "mode": "exact", "timeout_ms": 5000 },
  "graphs": [
    {
      "id": "pair-1",
      "g1": { "graphRef": "/v1/graphs/grf_9f1c2e..." },
      "g2": { "graphRef": "/v1/graphs/grf_a02b7f..." }
    }
  ]
}
```

Note: `graphRef` resolution is intended for integration with a companion Graph-Generation service. Currently only the inline format (nodes/edges) is supported.

#### Batch for graphs

Multiple pairs can also be submitted in one request:

```json
{
  "algorithm": "ged_astar",
  "backend": "networkx",
  "params": { "mode": "exact", "timeout_ms": 5000 },
  "graphs": [
    { "id": "pair-1", "g1": { "nodes": [...] }, "g2": { "nodes": [...] } },
    { "id": "pair-2", "g1": { "nodes": [...] }, "g2": { "nodes": [...] } }
  ]
}
```

### Output format (GED)

```json
{
  "output": {
    "includeNodeMap": true
  }
}
```

With `includeNodeMap: true` the response will include the optimal node-mapping path (supported by NetworkX `mode: "path"` and GEDLIB).

## Text Algorithms

| Algorithm Tag | Backend Options | Families | Result Type |
|---------------|----------------|----------|-------------|
| `levenshtein` | rapidfuzz, textdistance, jellyfish, edlib | Levenshtein distance | scalar_distance |
| `damerau_levenshtein` | rapidfuzz, textdistance, jellyfish | Damerau-Levenshtein | scalar_distance |
| `hamming` | rapidfuzz, textdistance, jellyfish | Hamming distance | scalar_distance |
| `jaro_winkler` | rapidfuzz, textdistance, jellyfish | Jaro / Jaro-Winkler | scalar_distance |
| `osa` | rapidfuzz | Optimal String Alignment | scalar_distance |
| `indel` | rapidfuzz, textdistance | Indel (LCS-based distance) | scalar_distance |
| `lcs` | textdistance | Longest Common Subsequence | sequence |
| `needleman_wunsch` | textdistance | Needleman-Wunsch global alignment | alignment |
| `gotoh` | textdistance | Gotoh affine-gap alignment | scalar_distance |
| `smith_waterman` | textdistance | Smith-Waterman local alignment | scalar_distance |
| `token_set_similarity` | textdistance | Jaccard, Sørensen-Dice, Tversky, Cosine | scalar_distance |
| `ncd` | textdistance | Normalized Compression Distance | scalar_distance |
| `phonetic_encoding` | jellyfish | Soundex, Metaphone, NYSIIS | phonetic_code |
| `long_sequence_alignment` | edlib | Banded/bit-vector alignment + CIGAR | alignment |
| `diff_patch` | diff_match_patch | Myers diff / edit-script + patch | edit_script |

## Graph Algorithms

| Algorithm Tag | Backend Options | Families | Result |
|---------------|----------------|----------|--------|
| `ged_astar` | networkx, gedlib | Exact GED, anytime approx, edit-path retrieval | upper/lower bound, node_map |
| `ged_heuristic` | gedlib, gmatch4py | Bipartite, IPFP, REFINE, lower bounds | upper/lower bound |
| `ged_hausdorff` | gmatch4py | Hausdorff Edit Distance | distance |
| `ged_greedy` | gmatch4py | Greedy edit distance | distance |

## Request/Response Examples

### Levenshtein (RapidFuzz)

```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "levenshtein",
    "backend": "rapidfuzz",
    "params": {},
    "inputs": [
      {"id": "pair-1", "a": "kitten", "b": "sitting"}
    ]
  }'
```

Response:

```json
{
  "algorithm": "levenshtein",
  "backend": "rapidfuzz",
  "result_type": "scalar_distance",
  "results": [
    { "id": "pair-1", "value": 3.0, "normalized": 0.4286 }
  ],
  "meta": { "compute_time_ms": 5.1 }
}
```

### Jaro-Winkler (RapidFuzz)

```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "jaro_winkler",
    "backend": "rapidfuzz",
    "params": {},
    "inputs": [
      {"id": "pair-1", "a": "MARTHA", "b": "MARHTA"}
    ]
  }'
```

Response:

```json
{
  "algorithm": "jaro_winkler",
  "backend": "rapidfuzz",
  "result_type": "scalar_distance",
  "results": [
    { "id": "pair-1", "value": 0.9611, "normalized": 0.9611 }
  ],
  "meta": { "compute_time_ms": 2.3 }
}
```

### Batch text comparison

```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "levenshtein",
    "backend": "rapidfuzz",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "kitten", "b": "sitting"},
      {"id": "p2", "a": "flaw", "b": "lawn"},
      {"id": "p3", "a": "hello", "b": "world"}
    ]
  }'
```

### Phonetic encoding

```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "phonetic_encoding",
    "backend": "jellyfish",
    "params": {"scheme": "soundex"},
    "inputs": [
      {"id": "w1", "text": "Jellyfish"}
    ]
  }'
```

Response:

```json
{
  "algorithm": "phonetic_encoding",
  "backend": "jellyfish",
  "result_type": "phonetic_code",
  "results": [
    { "id": "w1", "codes": { "soundex": "J412" } }
  ],
  "meta": { "compute_time_ms": 0.5 }
}
```

### Diff/Patch

```bash
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "diff_patch",
    "backend": "diff_match_patch",
    "params": {},
    "inputs": [
      {"id": "p1", "a": "The quick brown fox", "b": "The slow brown fox"}
    ]
  }'
```

### GED — exact mode (NetworkX)

```bash
curl -X POST http://localhost:8000/v1/graphs/ged/compute \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "ged_astar",
    "backend": "networkx",
    "params": { "mode": "exact", "timeout_ms": 5000 },
    "graphs": [
      {
        "id": "pair-1",
        "g1": {
          "nodes": [{"id": "A"}, {"id": "B"}],
          "edges": [{"source": "A", "target": "B"}]
        },
        "g2": {
          "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
          "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
        }
      }
    ]
  }'
```

## Result Types

| result_type | Description | Example fields |
|-------------|-------------|----------------|
| `scalar_distance` | Numeric distance or similarity | value, normalized |
| `sequence` | Extracted subsequence (e.g. LCS) | value, length |
| `phonetic_code` | Phonetic encoding result | codes (dict per scheme) |
| `edit_script` | Line/character-level diff with operations | diffs, levenshtein |
| `alignment` | Sequence alignment with CIGAR | edit_distance, cigar |

## Development

```bash
make prep              # Install dev dependencies
make test              # Run all tests (pytest -v)
make lint              # Lint code (ruff)
make start             # Start dev server with hot reload
make generate-openapi  # Generate OpenAPI spec
make docker-build      # Build Docker image
```

### Run specific tests

```bash
pytest -v tests/test_text_compare.py      # Text algorithm tests only
pytest -v tests/test_graph_compare.py     # Graph algorithm tests only
pytest -v tests/test_integration.py       # HTTP layer tests only
pytest -v -k "test_jaro_winkler"          # Single test
pytest -v -k "TestNetworkXGedAStar"       # Single test class
```

## Docker

```bash
docker-compose -f docker-compose.dev.yml up --build   # Development
docker-compose -f docker-compose.prod.yml up --build  # Production
```

## Quick Start

```bash
# 1. Install
cd services/edit-distance-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Run tests
pytest -v

# 3. Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Send a request (in another terminal)
curl http://localhost:8000/v1/text/algorithms
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"levenshtein","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}'

# 5. Smoke test
bash tests/test_smoke.sh http://localhost:8000
```

## Architecture

The service follows the same patterns as the `noise-generation-service`:

- **Discriminated union request body** — one `POST` endpoint per domain, algorithm selected via `algorithm` field
- **Backend is explicit** — different libraries can produce numerically different results for the same named algorithm
- **Discovery endpoint** — `GET /v1/*/algorithms` exposes the full catalog at runtime
- **Result shape varies** — response is a discriminated union on `result_type` (scalar_distance, sequence, phonetic_code, edit_script, alignment)
- **Batching** — all compute endpoints accept arrays of inputs/graphs

### Algorithm/Backend Selection Rationale

The library set is derived from a **weighted maximum-coverage analysis** — a greedy approximation that minimizes the number of libraries while maximizing distinct algorithm-family coverage:

**Text ED** (15 families):
1. **textdistance** — 11 families, broadest coverage (Needleman-Wunsch, Gotoh, Smith-Waterman, token measures, NCD, LCS)
2. **RapidFuzz** — adds OSA, highest-performance C++ core (optimal for hot paths)
3. **jellyfish** — adds phonetic encoding (Soundex, Metaphone, NYSIIS)
4. **edlib** — adds long-sequence banded alignment with CIGAR
5. **diff-match-patch** — adds Myers diff/patch edit-script output

**Graph ED** (10 families):
1. **NetworkX** — exact A* GED, anytime approximation, pure Python
2. **GEDLIB** — adds bipartite, IPFP, REFINE, lower-bound heuristics, MIP exact (C++ core)
3. **GMatch4py** — adds Hausdorff Edit Distance and Greedy ED (Cython, native networkx.Graph)

## Project Structure

```
services/edit-distance-service/
├── pyproject.toml           # Project config & dependencies
├── Dockerfile               # Multi-stage Docker build
├── Makefile                 # Build/test/run commands
├── README.md                # This file
├── docker-compose.dev.yml   # Dev Docker Compose
├── docker-compose.prod.yml  # Prod Docker Compose
├── .gitignore
├── src/
│   ├── main.py              # FastAPI app & HTTP endpoints
│   ├── models.py            # Pydantic request/response models
│   ├── cli.py               # Click CLI (serve, list, compare, openapi)
│   ├── text/
│   │   └── __init__.py      # Text ED implementations (dispatcher pattern)
│   └── graph/
│       └── __init__.py      # Graph ED implementations (dispatcher pattern)
├── tests/
│   ├── test_text_compare.py     # Unit tests — all 15 text algorithms
│   ├── test_graph_compare.py    # Unit tests — all 4 GED algorithm tags
│   ├── test_integration.py      # Integration tests — HTTP layer
│   └── test_smoke.sh            # Bash smoke test script
└── http-tests/
    ├── text_algorithms.http     # VS Code REST Client examples
    ├── graph_algorithms.http
    └── health.http
```

## GitHub Actions CI

A CI pipeline is defined in `.github/workflows/service-edit-distance-service.yml`:

1. **lint** — `ruff check src/` (Python 3.12)
2. **test** — `pytest -v` + smoke test with running server
3. **generate-openapi** — auto-generates OpenAPI 3.1 spec
4. **build** — builds & pushes Docker image to `ghcr.io` (master only)
