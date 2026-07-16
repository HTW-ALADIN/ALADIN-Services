# ALADIN-Functions Monorepo

[![License: MIT](https://img.shields.io/github/license/HTW-ALADIN/ALADIN-Services)](LICENSE)
[![graph-rewriting-service CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-graph-rewriting-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-graph-rewriting-service.yml)
[![jsonpath-mapper-service CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-jsonpath-mapper-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-jsonpath-mapper-service.yml)
[![sql-assessment-service CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-sql-assessment-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-sql-assessment-service.yml)
[![fermentaladin-service CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-fermentaladin-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-fermentaladin-service.yml)

## Services

| Service | Language | CI | Coverage | Description |
| ------- | -------- | -- | -------- | ----------- |
| [graph-rewriting-service](services/graph-rewriting-service/README.md) | TypeScript | [![CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-graph-rewriting-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-graph-rewriting-service.yml) | [![codecov](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services/graph/badge.svg?flag=graph-rewriting-service)](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services?flags[0]=graph-rewriting-service) | Graph Rewriting as a Service — SPO graph transformations backed by Neo4j |
| [jsonpath-mapper-service](services/jsonpath-mapper-service/README.md) | TypeScript | [![CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-jsonpath-mapper-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-jsonpath-mapper-service.yml) | [![codecov](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services/graph/badge.svg?flag=jsonpath-mapper-service)](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services?flags[0]=jsonpath-mapper-service) | JSONPath Mapper — JSON-to-JSON transformation utility exposed as a Fastify HTTP API |
| [sql-assessment-service](services/sql-assessment-service/README.md) | TypeScript | [![CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-sql-assessment-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-sql-assessment-service.yml) | [![codecov](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services/graph/badge.svg?flag=sql-assessment-service)](https://codecov.io/gh/HTW-ALADIN/ALADIN-Services?flags[0]=sql-assessment-service) | SQL Assessment — schema analysis, SQL task generation, and query grading |
| [fermentaladin-service](services/fermentaladin-service/README.md) | Python | [![CI](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-fermentaladin-service.yml/badge.svg)](https://github.com/HTW-ALADIN/ALADIN-Services/actions/workflows/service-fermentaladin-service.yml) | — | Bioreactor fermentation simulation — ODE-based multi-phase kinetic model exposed as a FastAPI HTTP service |

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
├── .pre-commit-config.yaml          # Local pre-commit and pre-push hooks
├── .secrets.baseline                # detect-secrets known-findings baseline
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
    branches: ["master"]
    paths:
      - "services/<new-service>/**"
  pull_request:
    branches: ["master"]
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
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: services/<new-service>/coverage/lcov.info
          flags: <new-service>
          token: ${{ secrets.CODECOV_TOKEN }}
          fail_ci_if_error: false
        if: always()

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

---

### Local Development — Pre-commit Hooks

This repository uses [`pre-commit`](https://pre-commit.com/) to enforce code quality locally before code reaches CI. Hooks run automatically on `git commit` (fast checks) and `git push` (full test suite).

#### What the hooks do

| Stage | Hook | What it checks |
| ----- | ---- | -------------- |
| `pre-commit` | `detect-secrets` | Blocks accidental credential/secret commits |
| `pre-commit` | `prettier` | Format check (graph-rewriting-service) |
| `pre-commit` | `eslint-*` | ESLint on changed TypeScript files per service |
| `pre-commit` | `tsc-*` | TypeScript type-check (`tsc --noEmit`) per service |
| `pre-push` | `test-all` | Full test suite (`make test`) across all services |

Tests run on push rather than commit to keep local commits fast. The graph-rewriting-service tests require Docker (Testcontainers spins up a Neo4j instance).

#### Setup

1. **Install `pre-commit`** (requires Python 3.8+):

   ```sh
   pip install pre-commit
   ```

2. **Install dependencies** for all services so the `system`-language hooks can find `eslint`, `tsc`, etc.:

   ```sh
   make prep
   ```

3. **Register the hooks** with Git:

   ```sh
   pre-commit install                        # pre-commit hook
   pre-commit install --hook-type pre-push   # pre-push hook (tests)
   ```

4. **Verify** by doing a dry run against all files:

   ```sh
   pre-commit run --all-files
   ```

#### Managing the secrets baseline

`detect-secrets` stores a baseline of known/accepted findings in `.secrets.baseline`. If a scan flags a false positive, audit and accept it:

```sh
detect-secrets scan --exclude-files 'package-lock\.json' > .secrets.baseline
git add .secrets.baseline
```

To update hook versions to their latest revisions:

```sh
pre-commit autoupdate
```
