IMAGE_NAME  := academic-search-service
OPENAPI_OUT := academic-search-service.openapi.json
PORT        ?= 8003

.PHONY: prep build test lint start cli clean docker-build generate-openapi

## prep: Install all dependencies (including dev)
prep:
	uv sync

## build: No compile step required for Python
build:
	@echo "No build step required for Python"

## test: Run the full test suite with coverage
test:
	uv run pytest --cov=src --cov-report=xml --cov-report=term-missing

## lint: Run ruff linter and format checker
lint:
	uv run ruff check src/ test/
	uv run ruff format --check src/ test/

## start: Start the FastAPI server locally with hot-reload
start:
	uv run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT) --app-dir src

## cli: Invoke the CLI (pass args via ARGS, e.g. `make cli ARGS="search --query ..."`)
cli:
	uv run python -m cli $(ARGS)

## clean: Remove build and test artifacts
clean:
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

## docker-build: Build the Docker image
docker-build:
	docker build -t $(IMAGE_NAME) .

## generate-openapi: Generate the OpenAPI spec to $(OPENAPI_OUT)
generate-openapi:
	uv run python src/generate_openapi.py
