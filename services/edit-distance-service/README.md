# Edit Distance Service

Unified microservice for **text edit distance** and **graph edit distance (GED)** algorithms, following the same architecture as the noise-generation-service.

## Library Selection

### Text Edit Distance (15 algorithm families)

| Tier | Libraries | Coverage | 
|------|-----------|----------|
| **Tier 1** (core) | **RapidFuzz** + **textdistance** + **jellyfish** | **13/15 (87%)** |
| **Tier 2** (full) | + **edlib** + **diff-match-patch** | **15/15 (100%)** |

### Graph Edit Distance (10 algorithm families)

| Tier | Libraries | Coverage |
|------|-----------|----------|
| **Tier 1** (core) | **NetworkX** + **GEDLIB** (via gedlibpy) | **8/10 (80%)** |
| **Tier 2** (full) | + **GMatch4py** | **10/10 (100%)** |

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
| `POST` | `/v1/graphs/ged/compute` | Compute GED (synchronous, returns 201) |
| `GET` | `/v1/graphs/ged/{resultId}` | Retrieve a stored result |
| `DELETE` | `/v1/graphs/ged/{resultId}` | Release a stored result |

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
| `ged_astar` | networkx, gedlib | Exact GED, anytime approx, edit-path retrieval | (upper/lower bound, node map) |
| `ged_heuristic` | gedlib, gmatch4py | Bipartite, IPFP, REFINE, lower bounds | (upper/lower bound) |
| `ged_hausdorff` | gmatch4py | Hausdorff Edit Distance | (distance) |
| `ged_greedy` | gmatch4py | Greedy edit distance | (distance) |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Send a request
curl -X POST http://localhost:8000/v1/text/compare \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"levenshtein","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}'

# List all text algorithms
curl http://localhost:8000/v1/text/algorithms | jq .
```

## Development

```bash
make prep     # Install dev dependencies
make test     # Run tests
make lint     # Lint code
make start    # Start dev server with hot reload
make generate-openapi  # Generate OpenAPI spec
make docker-build      # Build Docker image
```

## Docker

```bash
# Development
docker-compose -f docker-compose.dev.yml up --build

# Production
docker-compose -f docker-compose.prod.yml up --build
```

## Architecture

The service follows the same patterns as the noise-generation-service:

- **Discriminated union request body** — one `POST` endpoint per domain, algorithm selected via `algorithm` field
- **Backend is explicit** — different libraries can produce numerically different results for the same named algorithm
- **Discovery endpoint** — `GET /v1/*/algorithms` exposes the full catalog at runtime
- **Result shape varies** — response is a discriminated union on `result_type` (scalar_distance, sequence, phonetic_code, edit_script, alignment)
- **Batching** — all compute endpoints accept arrays of inputs/graphs

### Algorithm/Backend Selection Rationale

See [edit-distance-libraries-comparison.md](./docs/edit-distance-libraries-comparison.md) for the full weighted maximum-coverage analysis.

**Text ED** — Greedy approximation solving the weighted maximum coverage problem:
1. textdistance (11 families, Q=0.810)
2. RapidFuzz (1 new family: OSA, Q=1.000)
3. jellyfish (1 new family: phonetic, Q=0.765)
4. edlib (1 new family: long-sequence, Q=0.303)
5. diff-match-patch (1 new family: diff/patch, Q=0.275)

**Graph ED** — Same approach:
1. NetworkX (3 families, Q=1.000)
2. GEDLIB (5 new families, Q=0.260)
3. GMatch4py (2 new families, Q=0.360)