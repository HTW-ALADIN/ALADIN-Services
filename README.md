# ALADIN-Functions Monorepo

## Services

| Service                                                               | Language   | Description                                                              |
| --------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| [graph-rewriting-service](services/graph-rewriting-service/README.md)     | TypeScript | Graph Rewriting as a Service — SPO graph transformations backed by Neo4j |
| [jsonpath-mapper-service](services/jsonpath-mapper-service/README.md)     | TypeScript | JSONPath Mapper — JSON-to-JSON transformation utility exposed as a Fastify HTTP API |
| [sql-assessment-service](services/sql-assessment-service/README.md)       | TypeScript | SQL Assessment — schema analysis, SQL task generation, and query grading |

## For Developers:

This repository is a polyglot monorepo. Each service lives in its own directory under `services/` and is fully self-contained with its own dependencies, tests, and build pipeline. Services written in the same language may share code via the `packages/` directory.

### Repository structure

```
ALADIN-Functions/
├── services/                        # One directory per service
│   └── <service-name>/
│       ├── src/                     # Service source code
│       ├── Makefile                 # Standard targets: build, test, lint, start, clean, docker-build, generate-openapi
│       ├── <lang-manifest>          # package.json / pyproject.toml / Cargo.toml / etc.
│       ├── Dockerfile               # (optional) container image
│       ├── docker-compose.yml       # (optional) local dev dependencies
│       └── README.md                # Service-specific documentation
│
├── packages/                        # Shared code, grouped by language
│   ├── typescript/                  # Shared TypeScript packages
│   │   └── <package-name>/          # Referenced as a local path dep by TS services
│   └── python/                      # Shared Python packages
│       └── <package-name>/          # Referenced as a local path dep by Python services
│
├── .github/
│   └── workflows/
│       └── service-<name>.yml       # Per-service CI workflow (path-filtered)
│
├── Makefile                         # Root orchestrator — delegates to all service Makefiles
├── .editorconfig                    # Shared editor baseline (polyglot)
├── .gitignore                       # Root-level ignores (polyglot)
└── README.md                        # This file
```

### Root Makefile targets

Run a target across **all** services and packages at once:

```sh
make prep              # Preps every service, e.g. installing dependencies
make build             # Build every service
make test              # Test every service
make lint              # Lint every service
make clean             # Remove all build artifacts
make docker-build      # Build Docker images for every service
make generate-openapi  # Generate OpenAPI specs for every service
```

Target a **single** service directly:

```sh
make -C services/<service-name> build
make -C services/<service-name> test
```

### Service Makefile contract

Every service must expose these targets in its own `Makefile`:

| Target             | Description                        |
| ------------------ | ---------------------------------- |
| `prep`             | Prep service, e.g. install deps    |
| `build`            | Compile or bundle the service      |
| `test`             | Run all tests (unit + integration) |
| `lint`             | Run linters and formatters         |
| `start`            | Start the service locally          |
| `clean`            | Remove build artifacts             |
| `docker-build`     | Build the service's Docker image   |
| `generate-openapi` | Generate the OpenAPI spec          |

Each service uses its own language-native tooling internally (`npm`, `pip`, `cargo`, etc.). The `Makefile` is the uniform interface that the root orchestrator calls.

### Adding a new service

1. Create `services/<new-service>/`
2. Add a `Makefile` with the five standard targets above
3. Add a `.github/workflows/service-<new-service>.yml` with a `paths:` filter scoped to `services/<new-service>/**`
4. Add a `README.md` describing the service

#### CI workflow template

```yaml
name: <new-service>

on:
  push:
    branches: ["main"]
    paths:
      - "services/<new-service>/**"
  pull_request:
    branches: ["main"]
    paths:
      - "services/<new-service>/**"

defaults:
  run:
    working-directory: services/<new-service>

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... language setup ...
      - run: make lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      # ... language setup ...
      - run: make test

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      # ... language setup ...
      - run: make build
```

### Adding shared code

When two or more services in the same language need to share code, add a package under `packages/<language>/<package-name>/`. Give it the same `Makefile` contract (`build`, `test`, `lint`, `clean`) so the root orchestrator can target it too.

Reference the shared package from a service using a local path dependency:

- **TypeScript:** `"dependencies": { "@repo/shared": "file:../../packages/typescript/shared" }`
- **Python:** `dependencies = [{ path = "../../packages/python/shared", editable = true }]` in `pyproject.toml`
