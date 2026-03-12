IMAGE_NAME  := fermentaladin-service
OPENAPI_OUT := fermentaladin-service.openapi.json
PORT        ?= 8000

.PHONY: prep build test lint start clean docker-build generate-openapi

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
	uv run uvicorn api:app --reload --port $(PORT) --app-dir src

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
