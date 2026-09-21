# Text Template Service

A stateless REST and CLI wrapper around
[MiniJinja 2.24.0](https://github.com/mitsuhiko/minijinja). It renders arbitrary
text from Jinja-compatible templates and JSON context while keeping templates,
includes, and inheritance inside an in-memory request boundary.

## Engine selection and wrapper rationale

MiniJinja already provides an embeddable Rust API and a standalone
`minijinja-cli`, but it does not provide the REST API or OpenAPI contract
required by this repository. This service therefore embeds MiniJinja and adds
only the required REST/OpenAPI layer and a mirroring CLI. Template parsing,
evaluation, filters, tests, includes, inheritance, and macros remain delegated
to MiniJinja rather than being reimplemented by the wrapper.

## Public contract

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Container and process health |
| `GET` | `/v1/capabilities` | Engine version, supported features, and active limits |
| `POST` | `/v1/render` | Render an inline template or template bundle |
| `GET` | `/api-docs/openapi.json` | Generated OpenAPI document |

The REST API accepts `application/json`. Render responses use JSON by default;
send `Accept: text/plain` to receive the rendered text directly. Errors use
`application/problem+json`.

### Inline rendering

```sh
curl -s http://localhost:8000/v1/render \
  -H 'Content-Type: application/json' \
  -d '{
    "source": {
      "kind": "inline",
      "template": "Hello {{ user.name }}!"
    },
    "context": {
      "user": {"name": "World"}
    }
  }'
```

### Bundle rendering

Bundles support includes, imports, macros, inheritance, and blocks without
granting access to files in the service container.

```json
{
  "source": {
    "kind": "bundle",
    "entrypoint": "message.txt",
    "templates": {
      "message.txt": "{% include 'header.txt' %}\nHello {{ name }}",
      "header.txt": "Generated message"
    }
  },
  "context": {"name": "World"},
  "options": {
    "undefined": "strict",
    "autoescape": "none",
    "keepTrailingNewline": true
  }
}
```

`strict`, `none`, and `true` are the default option values. Public requests
cannot install native functions, filters, tests, loaders, or execution limits.

## CLI

The CLI calls the same renderer as the REST endpoint. Context and template
reads, bundle file counts and directory traversal, and logical template names
are bounded before rendering.

```sh
cargo run -- render --template template.j2 --context context.json

cat template.j2 | cargo run -- render --template - --context context.json

cargo run -- render \
  --template-dir ./templates \
  --entrypoint message.txt \
  --context context.json
```

Rendered text is written to stdout. Structured problem details are written to
stderr and failures return a non-zero exit code. A template and context cannot
both use stdin. Bundle directory symlinks are rejected.

## Run locally

```sh
make prep
make test
make coverage
make start
```

`make coverage` uses `cargo-llvm-cov` and fails unless the testable library
surface has at least 80% line coverage (override with `COVERAGE_THRESHOLD`).
The small `src/main.rs` process bootstrap is excluded from that percentage; its
CLI exit paths are exercised by integration tests and the long-running server
path is covered by the Docker smoke test.

The server listens on `0.0.0.0:8000` by default. Override it with:

```sh
cargo run -- server --host 127.0.0.1 --port 8080
```

## Docker

```sh
make docker-build
docker run --rm -p 8000:8000 text-template-service
```

Run the complete image smoke test with `make docker-smoke`.

## Resource and security model

REST rendering uses only template strings supplied in the request. It does not
configure a filesystem loader, expose host objects, load caller-defined native
extensions, use persistent storage, or make outbound network requests.

The following server-owned limits can be configured through environment
variables:

| Variable | Default |
| --- | ---: |
| `TEXT_TEMPLATE_MAX_BODY_BYTES` | 2,097,152 |
| `TEXT_TEMPLATE_MAX_CONTEXT_BYTES` | 1,048,576 |
| `TEXT_TEMPLATE_MAX_TEMPLATE_BYTES` | 262,144 per template |
| `TEXT_TEMPLATE_MAX_BUNDLE_TEMPLATES` | 32 |
| `TEXT_TEMPLATE_MAX_TEMPLATE_NAME_BYTES` | 255 |
| `TEXT_TEMPLATE_MAX_CONCURRENT_RENDERS` | 4 |
| `TEXT_TEMPLATE_MAX_OUTPUT_BYTES` | 1,048,576 |
| `TEXT_TEMPLATE_FUEL` | 250,000 instructions |
| `TEXT_TEMPLATE_RECURSION_LIMIT` | 100 |
| `TEXT_TEMPLATE_TIMEOUT_MS` | 2,000 |

Output is bounded while it is rendered rather than after allocating the full
result. Fuel and recursion bounds terminate expensive template execution. The
wall-clock timeout bounds the HTTP wait; fuel remains the hard in-process
execution bound for the synchronous renderer. Concurrent render work is capped;
requests receive `503 Service Unavailable` while every render slot is occupied.

The built-in `indent`, `tojson`, and `format` filters are wrapped with bounded
equivalents: a single filter value may not materialize more than the default
output limit (1,048,576 bytes) before rendering stops, oversized `tojson`
pretty-print widths are rejected, and printf field widths/precisions in
`format` are clamped to 256 characters. These safeguards exist because the
upstream engine performs unbounded single allocations for those widths; a
deployment that raises `TEXT_TEMPLATE_MAX_OUTPUT_BYTES` above its default keeps
these per-filter ceilings.

## Hardware requirements

- CPU: no special instruction set beyond the selected Linux build target
- GPU: not required
- Memory: governed by the configured request, context, bundle, and output limits
- Persistent storage: not required
- Outbound network: not required at runtime
- Published target: `linux/amd64`; additional architectures may be added later

There is no justified fixed minimum RAM requirement. Establish one only from a
benchmark using the deployed limit configuration.

## Development contract

The service implements every monorepo Makefile target:

```sh
make prep
make build
make test
make coverage
make lint
make start
make clean
make docker-build
make generate-openapi
```

The generated OpenAPI file is written to `openapi/openapi.yaml`. Tests cover
the wrapper contract, limits, REST/CLI behavior, and container operation; they
do not duplicate MiniJinja's upstream unit suite.
