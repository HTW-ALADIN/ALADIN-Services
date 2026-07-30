.PHONY: prep build test lint start clean docker-build docker-run generate-openapi

SHELL := /bin/bash
SERVICE := sagemath-wrapper

prep:
	@pip install -e ".[test]"

build:
	@echo "Build not yet implemented"

test:
	@python -m pytest tests/

lint:
	@ruff check src/ tests/

start:
	@echo "Start not yet implemented"

clean:
	@rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-build:
	@docker build -t $(SERVICE) .

docker-run:
	@docker run --rm -p 8000:8000 $(SERVICE)

generate-openapi:
	@python scripts/export_openapi.py --out openapi/openapi.yaml