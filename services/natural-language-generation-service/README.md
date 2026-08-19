# Natural Language Generation Service

A stateless REST and CLI service for deterministic rule-based natural language
generation. It combines:

- [jsRealB 5.5.0](https://github.com/rali-udem/jsRealB) for English and French
  surface realisation from constituent or dependency JSON; and
- [RosaeNLG 4.4.0](https://github.com/RosaeNLG/rosaenlg) for trusted
  template/data-to-text generation in English, French, German, Italian, and
  Spanish.

This is the full-coverage Tier 2 design from the project research. It is one
service specification with two generation modes, not two separately deployed
service variants. Together, the selected engines directly cover all 15 of the
research capability families.

## Selection and capability coverage

jsRealB is the primary, actively maintained dependency. RosaeNLG supplies the
two net-new capability families—higher-level anaphora and lexical variation—
needed to move from 13/15 to 15/15 direct coverage. RosaeNLG was deprecated and
archived in March 2026, so the template backend is kept behind a distinct mode
and its archived status is exposed by the capabilities endpoint.

|   # | Capability family                               | Direct backend            |
| --: | ----------------------------------------------- | ------------------------- |
|   1 | Structured deterministic generation             | jsRealB, RosaeNLG         |
|   2 | Constituent realisation                         | jsRealB                   |
|   3 | Dependency realisation                          | jsRealB                   |
|   4 | Morphology and inflection                       | jsRealB, RosaeNLG         |
|   5 | Grammatical agreement                           | jsRealB, RosaeNLG         |
|   6 | Tense, aspect, and modality                     | jsRealB, RosaeNLG         |
|   7 | Clause and sentence transformations             | jsRealB                   |
|   8 | Coordination, enumeration, and aggregation      | jsRealB, RosaeNLG         |
|   9 | Punctuation, capitalization, and orthography    | jsRealB, RosaeNLG         |
|  10 | Numbers, dates, ordinals, and formatted values  | jsRealB, RosaeNLG         |
|  11 | Higher-level anaphora and referring expressions | RosaeNLG                  |
|  12 | Lexical variation and synonym selection         | RosaeNLG                  |
|  13 | Multi-sentence and document composition         | jsRealB, RosaeNLG         |
|  14 | Multiple supported languages                    | jsRealB, RosaeNLG         |
|  15 | JSON-oriented REST input                        | jsRealB, RosaeNLG wrapper |

The service does not include SimpleNLG because it adds a JVM and substantial
adapter code without adding a missing capability to this selected pair.

## Why a wrapper is still required

jsRealB exposes the required `fromJSON(...).realize()` operation, but its
upstream examples do not implement this repository's validated REST, OpenAPI,
problem-detail, resource-limit, Docker, or CI contracts. RosaeNLG historically
shipped server and CLI tooling, but those packages are now archived and do not
provide the shared discriminated contract used here. The service therefore
keeps the wrapper thin: validate one common envelope, enforce repository
boundaries, dispatch to the selected engine, and normalize the response.

## Public API

| Method | Path                     | Purpose                                     |
| ------ | ------------------------ | ------------------------------------------- |
| `GET`  | `/healthz`               | Process liveness                            |
| `GET`  | `/v1/capabilities`       | Engines, modes, coverage, and active limits |
| `POST` | `/v1/generate`           | Generate text using either mode             |
| `GET`  | `/api-docs/openapi.json` | Generated OpenAPI 3.1 document              |
| `GET`  | `/api-docs`              | Swagger UI                                  |

Start the service and call the structured surface-realisation mode:

```sh
make prep
make start

curl --fail http://localhost:8000/v1/generate \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/plain' \
  --data-binary @examples/english-constituent.json
```

The result is `The cat chases the mouse.`

Call the trusted template mode:

```sh
curl --fail http://localhost:8000/v1/generate \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/plain' \
  --data-binary @examples/english-template.json
```

With the committed example and seed, the result is
`<p>Hi Alice. They are ready.</p>`.

Without `Accept: text/plain`, the endpoint returns a JSON response containing
the text, mode, backend, language, engine version, and mode-specific metadata.
Failures use `application/problem+json`.

## Request modes

`POST /v1/generate` uses a discriminated request union. The supported
mode/backend combinations are fixed; callers cannot select arbitrary engines.

### Surface realisation

```json
{
	"mode": "surface_realization",
	"backend": "jsrealb",
	"language": "en",
	"input": {
		"representation": "constituent",
		"structure": {
			"terminal": "N",
			"lemma": "cat"
		}
	}
}
```

`language` is `en` or `fr`, and `representation` is `constituent` or
`dependency`. Recursive node definitions and the complete allowlist of grammar
properties are defined in [`openapi/openapi.json`](openapi/openapi.json).
JavaScript expressions and arbitrary jsRealB method names are rejected.

### Template generation

```json
{
	"mode": "template_generation",
	"backend": "rosaenlg",
	"language": "en_US",
	"input": {
		"template": "p Hello #{name}!",
		"data": { "name": "Alice" },
		"seed": 0
	}
}
```

`language` is one of `en_US`, `fr_FR`, `de_DE`, `it_IT`, or `es_ES`. `data`
must contain JSON values. `seed` is an optional unsigned 32-bit integer and
defaults to `0`, making RosaeNLG's controlled variation reproducible.

## Security and trust boundary

The two modes have different trust requirements:

- `surface_realization` accepts data only. The service allowlists the jsRealB
  structures and properties it invokes; the upstream JavaScript-evaluation
  example path is not exposed.
- `template_generation` accepts RosaeNLG/Pug template source. Pug templates can
  execute JavaScript and therefore **must be authored and supplied only by
  trusted users**. This mode is not a sandbox and must never be exposed as an
  unauthenticated, multi-tenant template-execution endpoint.

The service rejects Pug `include` and `extends` directives and prevents data
from replacing renderer control options. These are boundary checks, not a
security sandbox. Each template runs in a dedicated Node.js worker thread with
a 512 MiB old-generation heap limit. The worker is terminated when
`NLG_TEMPLATE_TIMEOUT_MS` expires, so a looping template cannot block the REST
or CLI process indefinitely. Worker isolation limits availability failures; it
does not remove the template's operating-system permissions. Deploy the service
behind an authenticated gateway and restrict template mode to trusted callers.
If untrusted users only need to provide content, store templates under
application control and let users supply only their JSON data—or expose only
the surface-realisation mode.

The service itself does not persist requests. Generated text can contain
caller-provided content; consumers that insert it into HTML must apply
context-appropriate escaping.

## CLI

The CLI uses the same schemas, limits, and generation code as REST:

```sh
npm run cli -- generate --request examples/english-constituent.json
npm run cli -- generate --request examples/english-template.json
cat examples/french-dependency.json | npm run cli -- generate --request -
npm run cli -- generate --request examples/english-template.json --json
```

Generated text is written to stdout. Errors are JSON problem details on stderr
and produce a non-zero exit status.

## Errors

REST failures use `application/problem+json`; CLI failures use the same shape
on stderr. Each contains an HTTP-style `status`, a stable `code`, and a
human-readable `detail`.

| Code                | Status | Meaning                                                            |
| ------------------- | -----: | ------------------------------------------------------------------ |
| `invalid-request`   |    400 | The request does not match the schema or violates a boundary check |
| `invalid-json`      |    400 | CLI input is not valid JSON                                        |
| `input-error`       |    400 | The CLI could not read its requested input                         |
| `payload-too-large` |    413 | REST or CLI input exceeds `NLG_MAX_BODY_BYTES`                     |
| `resource-limit`    |    422 | Structure/data depth, value count, or output exceeds a limit       |
| `realisation-error` |    422 | The selected engine could not generate the text                    |
| `internal-error`    |    500 | An unexpected server or CLI failure occurred                       |

Unexpected internal details are not returned to REST clients.

### invalid-request

The request does not match the documented schema or violates an input boundary.

### invalid-json

CLI input is not valid JSON.

### input-error

The CLI could not read the requested input.

### payload-too-large

The REST or CLI input exceeds the configured body-size limit.

### resource-limit

Input depth, value count, output size, or template execution time exceeds an
active service limit.

### realisation-error

The selected NLG engine could not generate text from the validated request.

### internal-error

An unexpected service or worker failure occurred. REST responses do not expose
internal implementation details.

## Configuration and resource limits

| Environment variable      |   Default |
| ------------------------- | --------: |
| `HOST`                    | `0.0.0.0` |
| `PORT`                    |    `8000` |
| `NLG_MAX_BODY_BYTES`      | `1048576` |
| `NLG_MAX_NODES`           |    `1000` |
| `NLG_MAX_DEPTH`           |      `64` |
| `NLG_MAX_OUTPUT_BYTES`    | `1048576` |
| `NLG_TEMPLATE_TIMEOUT_MS` |    `5000` |

Schema validation additionally limits template length, individual strings,
collection sizes, lemmas, and formatting properties. `NLG_MAX_NODES` applies
to jsRealB structure nodes and RosaeNLG data values. Template workers also use
a fixed 512 MiB V8 old-generation heap limit.

## Docker and hardware

```sh
make docker-build
docker run --rm --publish 8000:8000 natural-language-generation-service
make docker-smoke
```

The multi-stage image runs as the unprivileged `node` user and contains only
compiled service code and production dependencies.

- General-purpose CPU; no accelerator or GPU required
- No persistent storage required
- No generation-time network dependency for the bundled engines
- Memory for Node.js, jsRealB and RosaeNLG language resources, and configured
  request/output limits

Neither upstream project publishes a formal minimum RAM requirement. A
numerical minimum should be established by measuring the container with the
limits and concurrency used by the target deployment.

## Development

Local development requires Node.js 22 or newer and npm. Docker and curl are
needed only for the container smoke test.

```sh
make prep
make lint
make build
make test
make generate-openapi
make docker-smoke
```

Tests cover schema validation, both engines, anaphora, lexical variation,
REST/CLI parity, errors, limits, OpenAPI, and Docker execution. The coverage
gate enforces 100% statement, branch, function, and line coverage for service
source code. Tests intentionally do not duplicate either upstream project's
linguistic test suite. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for dependency attribution
and licensing information.
