# dkpro-sidecar

> ⚠️ **OPTIONAL component.** This Java sidecar adds exactly 2 algorithm families
> (`topic_model`, `structural_stylistic`) to the
> [text-similarity-service](../), taking coverage from 14/16 → 16/16. It is **not
> required** for normal operation: the Python service works fully without it.

**Cost/benefit summary:**

| | |
|---|---|
| ✅ **Benefit** | Families 15–16 (topic-model LSA/ESA, structural/stylistic) — the only 2 families with no Python alternative |
| ❌ **Cost** | DKPro is Java + Apache UIMA, **not on Maven Central** (must build from source), ~8 years stale upstream, runs as a separate JVM process |
| ❌ **No new coverage** | The 2 backend extensions still routed (`tfidf_cosine`, `wordnet_similarity`) are alternatives to already-covered families; `token_set`/`lcs`/`phonetic` belong to removed char-distance families and are no longer routed |

Skip it entirely if 14/16 coverage is sufficient — nothing else in the service
depends on it.

## Purpose

This is an internal sidecar service, not a public API. The main
`text-similarity-service` (Python) routes requests with `backend: "dkpro"`
to this service. The public API contract is the same 4 endpoints as the
Python service.

> **Status:** skeleton scaffolded (Phase 5). The two DKPro families
> (topic_model, structural_stylistic) are implemented as placeholders (return 0.5).
> The 2 optional backend extensions still routed (`tfidf_cosine`,
> `wordnet_similarity`) are also registered — all return placeholder values
> until DKPro Similarity is built from source and added to the classpath.

## DKPro Dependency

DKPro Similarity artifacts are **not published on Maven Central**. To get
real implementations instead of placeholders:

1. Clone https://github.com/dkpro/dkpro-similarity
2. Build with `mvn install -DskipTests`
3. The artifacts will be available in your local Maven repository
4. Uncomment the DKPro dependencies in `pom.xml`
5. Implement the DKPro calls in `DkproSimilarityService.java`

## Development

Requires JDK 21+ and Maven.

```sh
make prep    # resolve dependencies
make build   # compile and package
make test    # run unit tests
make start   # start Spring Boot on :8100
```

## Endpoints

- `GET /v1/dkpro/health` — health check
- `POST /v1/dkpro/similarity` — compute similarity (internal)

## Supported Measures

| Measure | Variants | Description |
|---|---|---|
| `topic_model` | `lsa`, `esa` | Topic-model-based similarity |
| `structural_stylistic` | `ngram_containment`, `type_token_ratio`, `greedy_string_tiling` | Structural/stylistic text similarity |
| `token_set` | `jaccard` | Word n-gram Jaccard (optional backend extension) |
| `lcs` | `common_substring` | Longest Common Substring (optional) |
| `phonetic` | `editex` | Phonetic comparison (optional) |
| `tfidf_cosine` | `cosine` | Cosine similarity (optional) |
| `wordnet_similarity` | `path` | WordNet similarity (optional) |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SERVER_PORT` | `8100` | HTTP port |

## License

MIT