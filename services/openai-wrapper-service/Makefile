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
	uv run ruff check src/ test/
	uv run ruff format --check src/ test/

start:
	uv run uvicorn api:app --reload --port $(PORT) --app-dir src

clean:
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t $(IMAGE_NAME) .

generate-openapi:
	uv run python src/generate_openapi.py
