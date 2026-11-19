# workflow-control-service

Official Aladin workflow control image. It evaluates the workflow DSL control
steps that cannot be expanded deterministically by the compiler and returns the
value the runner applies after output collection.

The image is intentionally a thin, stateless CLI plus a small HTTP surface. It
does not read Redis, MongoDB, Docker, resources or business payloads beyond the
task data it is explicitly given.

## Modes

### `control`

Reads `{params, data}` and returns `StackOperations`:

- `branch` evaluates each `when` expression in order and pushes
  `{op: "call", block}` for the first match, else `elseBlock`, else a no-op.
- `forEach` resolves `over` to an array and pushes one `spawn` per element plus a
  trailing `join`. Each child payload is the parent task data with the element
  bound under `as`.

The compiler emits this mode as a normal runner step with `control: true` and
exactly one JSON output:

```json
{
  "op": "run",
  "execution": {
    "contract": "aladin-runner/v1",
    "mode": "stateless",
    "image": "ghcr.io/htw-aladin/workflow-control-service:latest",
    "argv": [
      "node",
      "/app/build/cli.js",
      "control",
      "{{input.payload}}",
      "{{output.control}}"
    ],
    "input": {
      "params": { "literal": { "kind": "branch", "cases": [] } },
      "data": { "path": "$" }
    },
    "outputs": [{ "name": "control", "path": "{{output.control}}", "format": "json" }],
    "control": true
  }
}
```

### `collect`

Reads `{params, joined}` and writes the ordered output array directly (normal
data step, not `control: true`):

```json
{
  "kind": "collect",
  "order": ["0", "1"],
  "output": "result"
}
```

`joined` is the materialized join state:

```json
{
  "slots": {
    "0": { "payload": { "result": 1 } },
    "1": { "payload": { "result": 2 } }
  }
}
```

The compiler emits the collect step with a single JSON output and a `merge`
path; the runner merges the returned array into task data. The current runner
does not yet expose join results to a follow-up step, so `collect` is prepared
for that runtime change and documented in the service README rather than wired
end to end yet.

## CLI

```sh
node build/cli.js control input.json output.json
node build/cli.js collect input.json output.json
node build/cli.js control - -          # stdin -> stdout
```

Control mode renders semantic failures as `{"fail":{"code","message","retryable"}}`
with exit code `0`; protocol failures (bad arguments, unreadable or malformed
input) exit `1` with a safe message on stderr. Collect mode exits `1` on
semantic failures because its output must be the data array.

## HTTP

```sh
GET  /health
GET  /openapi.json
POST /control  {"params": ..., "data": ...}
POST /collect  {"params": ..., "joined": ...}
```

Domain failures return `422`; malformed requests return `400`; request bodies are
limited to 1 MiB.

## Limits and security

- Expressions are data, never code: no `eval`, functions, loops or recursion.
- Only `data` and `literal` expression bindings are available. `param`, `item`,
  `session` and `element` bindings must be materialized into task data first.
- JSONPath supports only `$`, `.name`, `["name"]` and `[index]`; wildcards,
  filters and recursive descent are rejected.
- Expression depth is 64, evaluation is capped at 1000 nodes, branches at 256
  cases, and `forEach` at 100 items. Task data is capped at 1 MiB; the total
  pushed child payloads are capped at 4 MiB.
- Equality and containment comparisons are capped at 64 nesting levels and
  10,000 visited nodes; containment arrays are capped at 10,000 items.
- `forEach` pushes the whole spawn group at once. It fails closed with
  `UNSUPPORTED_CONCURRENCY` unless the item count fits within the declared
  `concurrency` upper bound; bounded scheduling beyond that needs runtime
  support.
- Joined child payloads that are still data references are rejected with
  `UNRESOLVED_JOINED_PAYLOAD`; the runtime must materialize them before collect.
  The current runner does not yet expose join results to a follow-up step, so
  collect is prepared but not wired end to end.

## Development

```sh
npm install
npm run lint
npm test
npm run build
npm run generate:openapi
```

`npm test` builds first and runs the compiled engine, CLI and HTTP tests with
Node's built-in test runner. There are no runtime dependencies.

Docker image:

```sh
docker build -t workflow-control-service .
docker run --rm -p 3000:3000 workflow-control-service
```

The runner uses the CLI directly; the HTTP server is for health checks and manual
evaluation. Run the CLI in the same container image as the service. The runner
image only needs Node.js and `/app/build/`.