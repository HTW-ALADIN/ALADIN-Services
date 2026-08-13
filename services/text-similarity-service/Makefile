.PHONY: prep build test lint start clean docker-build generate-openapi

SERVICE := text-similarity-service
OPENAPI_OUT := text-similarity-service.openapi.json
PORT ?= 8000

prep:
	pip install -e ".[dev]"

build:
	@echo "No build step required for Python"

test:
	pytest -v --tb=short

lint:
	ruff check src/
	ruff format --check src/

start:
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT) --reload

clean:
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .pytest_cache .coverage coverage.xml
	rm -rf *.egg-info
	rm -f $(OPENAPI_OUT)

docker-build:
	docker build -f Dockerfile -t $(SERVICE) .

generate-openapi:
	python -m src.generate_openapi