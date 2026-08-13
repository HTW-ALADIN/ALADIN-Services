# Conventions for the Text-Similarity Service

Derived from inspecting the three closest existing Python services (`edit-distance-service`,
`academic-search-service`, `sagemath-wrapper-service`) and the root monorepo conventions.

## 1. Dependency manager

**Inconsistent across Python services.** The closest sibling (`edit-distance-service`) uses
**plain pip + setuptools** (`pip install -e ".[dev]"` in the Makefile, `pyproject.toml` with
`setuptools.build_meta` build backend). The other two use different approaches:

| Service | Manager | Build backend |
|---|---|---|
| `edit-distance-service` | `pip install -e ".[dev]"` | `setuptools.build_meta` |
| `academic-search-service` | `uv sync` | `hatchling.build` |
| `sagemath-wrapper-service` | `pip install -e ".[test]"` | `setuptools.build_meta` |

**Decision:** Use **plain pip + setuptools** (matching `edit-distance-service`), since it is
the closest structural sibling (unified REST API wrapping multiple algorithm libraries) and
its dependency pattern avoids requiring `uv` or `hatch` to be pre-installed. The `[dev]`
optional-dependencies group will hold test/lint tooling.

## 2. Test framework

All three services use **pytest**. `edit-distance-service` uses `pytest -v` directly.
`academic-search-service` uses `pytest --cov=...`. `sagemath-wrapper-service` uses
`python -m pytest`.

**Decision:** Use **pytest + pytest-asyncio + httpx** (for async `TestClient`), matching
`edit-distance-service`'s pattern. `make test` runs `pytest -v --tb=short`.

## 3. `generate-openapi` implementation

**All services use introspection** (not hand-written specs). Two patterns exist:

- `edit-distance-service` (inline): `python -c "from src.main import app; ... get_openapi(...)"` in the Makefile
- `academic-search-service` (dedicated script): `src/generate_openapi.py` calling `app.openapi()`

**Decision:** Use the **dedicated script** pattern (`src/generate_openapi.py`), which is
cleaner for complex specs and matches `academic-search-service`'s approach — the
discriminated union in the text-similarity spec will benefit from explicit schema
registration before export.

## 4. Dockerfile base image pattern

Two-stage Dockerfiles are the established pattern:

- **Builder stage:** `python:3.11-slim` → installs build deps (gcc, git, etc.) → installs
  Python dependencies → copies source → builds wheel → installs wheel
- **Runtime stage:** `python:3.11-slim` → copies site-packages and binary from builder →
  sets `USER nobody` → runs `uvicorn src.main:app`

**Decision:** Follow the two-stage pattern exactly. No Python version constraint from
gmatch4py (unlike edit-distance-service), so we can use `python:3.12-slim` or keep
`python:3.11-slim` for consistency — prefer `python:3.12-slim` since there's no
`numpy.distutils` dependency holding us back.

## 5. Java precedent

**No Java/JVM service exists in the monorepo.** There is no `packages/java/` directory.
The `third_party/` directory contains C++ code (GEDLIB) with no Java service conventions
to copy. Java is a **greenfield addition** — the `text-similarity-dkpro-service` will need
to establish the Java convention for the monorepo: Maven/Gradle build, Makefile targets
mapped to the Java toolchain, and a JVM-based Dockerfile pattern.

## 6. Additional conventions (cross-cutting)

- **Source layout:** `src/` directory with `src/__init__.py` and modules under it
- **Test layout:** `tests/` directory at service root, with `tests/__init__.py`
- **Linting:** `ruff` (all three Python services use it; `edit-distance-service` uses
  `ruff check src/` and `ruff format --check src/`)
- **CLI:** `click` or `typer` for CLI entry points (if needed)
- **Health endpoint:** `GET /health` returning `{"status": "ok", "service": "..."}` —
  present in all services