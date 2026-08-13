# text-similarity-service

Unified REST API for text similarity — 23 algorithm families over 8 backends
(NLTK, RapidFuzz, sentence-transformers, gensim, scikit-learn, textdistance,
BERTScore, DKPro Similarity).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/text/algorithms` | Discovery — list all algorithm/backend combinations with metadata |
| `POST` | `/v1/text/distance` | Compute text similarity (synchronous, batch) |
| `POST` | `/v1/text/retrieval` | Rank query candidates (synchronous, batch) |
| `POST` | `/v1/text/lexical` | Look up lexical relations (synchronous, batch) |

All compute endpoints are synchronous and stateless: every request takes
`algorithm` (+ optional `backend`), `params` and a batch `inputs` list, and
returns one result per input. When `backend` is omitted, the algorithm's
default backend (marked `default: true` in `/v1/text/algorithms`) is
auto-selected.

## Algorithms

- **`/v1/text/distance`** (similarity) — two texts in, one normalized score out
  (Levenshtein … BERTScore). Inputs: `{"id", "a", "b"}`.
- **`/v1/text/retrieval`** (retrieval) — one query + candidates in, a ranked
  match list out (`fuzzy_extract`, `semantic_search`). Inputs:
  `{"id", "query", "candidates"}`.
- **`/v1/text/lexical`** (lexical_relations) — one word in, a set of related
  words out (`synonym`, `antonym`, `hypernym`). Inputs: `{"id", "word"}`.

## Example

```sh
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

```json
{
  "algorithm": "levenshtein",
  "backend": "nltk",
  "results": [
    {
      "id": "p1",
      "result": {
        "raw": 3,
        "similarity": 0.25,
        "distance": 3,
        "compute_time_ms": 0.05
      }
    }
  ],
  "meta": {"compute_time_ms": 0.05}
}
```

## DKPro Sidecar (optional)

Two measures — `topic_model` and `structural_stylistic` — and the optional
`backend: "dkpro"` variants on five other tags are implemented by a separate
Java service in [`dkpro-sidecar/`](dkpro-sidecar/), called internally via HTTP.

The Python service is fully functional without the sidecar: every other measure
works, and `GET /v1/text/algorithms` still lists the DKPro entries. A request to a
DKPro-backed measure returns a clean `502/503 problem+json` when the sidecar is
not running.

The sidecar requires building DKPro Similarity from source (`git clone
https://github.com/dkpro/dkpro-similarity && mvn install`), JDK 21 + Maven, and
an extra JVM process — enable it only if those two measures are a hard
requirement.

## Development

```sh
make prep    # install dependencies
make test    # run tests
make lint    # run ruff
make start   # run uvicorn on :8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEXT_SIMILARITY_DKPRO_URL` | `http://localhost:8100` | Base URL of the DKPro Java sidecar |

## Data Dependencies

- NLTK WordNet corpus (`nltk.download('wordnet')`) — required for
  `wordnet_similarity`, `synonym`, `antonym`, `hypernym`, `hyponym`.
- NLTK Information Content corpus — required for `wordnet_similarity` variants
  `res`/`jcn`/`lin`.

## License

MIT
