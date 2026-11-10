.PHONY: prep build test lint start clean docker-build generate-openapi dev prod

# Single source of truth for the pinned gmatch4py commit / Cython version
# (see gmatch4py.env) — also read by the Dockerfile and CI workflow.
include gmatch4py.env
GMATCH4PY_PKG := gmatch4py @ $(GMATCH4PY_REF)

# gmatch4py's setup.py imports numpy directly at build time (no
# pyproject.toml build-system declared), so it must be installed with
# --no-build-isolation once numpy/Cython are already present. Its compiled
# extensions unconditionally import `numpy.distutils` on package import,
# which requires the real stdlib `distutils` (setuptools' local shim is
# missing pieces numpy.distutils needs) — hence SETUPTOOLS_USE_DISTUTILS.
export SETUPTOOLS_USE_DISTUTILS := stdlib

prep:
	pip install -e ".[dev]"
	pip install "Cython==$(CYTHON_VERSION)"
	pip install --no-build-isolation "$(GMATCH4PY_PKG)"

build:
	pip install -e ".[dev]"
	pip install "Cython==$(CYTHON_VERSION)"
	pip install --no-build-isolation "$(GMATCH4PY_PKG)"

test:
	pytest -v

lint:
	ruff check src/
	ruff format --check src/

start:
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .venv venv
	rm -rf *.egg-info

generate-openapi:
	python -c "from src.main import app; import json; from fastapi.openapi.utils import get_openapi; spec = get_openapi(title=app.title, version=app.version, openapi_version=app.openapi_version, description=app.description, routes=app.routes); print(json.dumps(spec, indent=2))" > edit-distance-service.openapi.json

docker-build:
	docker build -f Dockerfile -t edit-distance-service ../..

dev:
	docker compose -f docker-compose.dev.yml up --build

prod:
	docker compose -f docker-compose.prod.yml up --build