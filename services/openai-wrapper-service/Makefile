IMAGE_NAME  := openai-wrapper-service
OPENAPI_OUT := openai-wrapper-service.openapi.json
PORT        ?= 8002

.PHONY: prep build test lint start clean docker-build generate-openapi

prep:
	uv sync

build:
	@echo "No build step required for Python"

test:
	uv run pytest --cov=src --cov-report=xml --cov-report=term-missing

lint:
	uv run ruff check src/ scripts/ test/
	uv run ruff format --check src/ scripts/ test/

start:
	uv run uvicorn openai_wrapper_service.api:app --reload --port $(PORT) --app-dir src

clean:
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t $(IMAGE_NAME) .

generate-openapi:
	uv run python scripts/generate_openapi.py
