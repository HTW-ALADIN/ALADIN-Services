IMAGE_NAME          := graph-generation-service
SIDECAR_IMAGE_NAME  := graph-tool-sidecar
OPENAPI_OUT := graph-generation-service.openapi.json
PORT        ?= 8002

.PHONY: prep build test lint start clean docker-build generate-openapi

prep:
	uv sync

build:
	uv build

test:
	uv run pytest --cov=src/app --cov=sidecar/src/graph_tool_sidecar --cov-report=xml --cov-report=term-missing

lint:
	uv run ruff check src/ sidecar/src/ test/
	uv run ruff format --check src/ sidecar/src/ test/
	uv run mypy src/ sidecar/src/ test/

start:
	uv run uvicorn app.main:app --reload --port $(PORT) --app-dir src

clean:
	rm -rf .coverage coverage.xml htmlcov/ .mypy_cache/ .pytest_cache/ .ruff_cache/ dist/ $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t $(IMAGE_NAME) .
	docker build -f sidecar/Dockerfile -t $(SIDECAR_IMAGE_NAME) .

generate-openapi:
	uv run python src/generate_openapi.py
