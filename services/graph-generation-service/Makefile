IMAGE_NAME  := graph-generation-service
OPENAPI_OUT := graph-generation-service.openapi.json
PORT        ?= 8002

.PHONY: prep build test lint start clean docker-build generate-openapi

prep:
	uv sync

build:
	uv build

test:
	uv run pytest --cov=src/app --cov-report=xml --cov-report=term-missing

lint:
	uv run ruff check src/ test/
	uv run ruff format --check src/ test/
	uv run mypy src/ test/

start:
	uv run uvicorn app.main:app --reload --port $(PORT) --app-dir src

clean:
	rm -rf .coverage coverage.xml htmlcov/ .mypy_cache/ .pytest_cache/ .ruff_cache/ dist/ $(OPENAPI_OUT)
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t $(IMAGE_NAME) .

generate-openapi:
	uv run python src/generate_openapi.py
