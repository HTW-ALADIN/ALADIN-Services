.PHONY: prep test lint start clean docker-build

PORT ?= 8200
REGISTRY ?= ghcr.io

prep:
	pip install -e ".[dev]"

test:
	pytest -v --tb=short

lint:
	ruff check src/
	ruff format --check src/

start:
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT) --reload

clean:
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .pytest_cache

docker-build:
	docker build -f Dockerfile -t $(REGISTRY)/conceptnet-sidecar .
