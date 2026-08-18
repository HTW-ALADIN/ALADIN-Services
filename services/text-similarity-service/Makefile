.PHONY: prep build test lint start clean docker-build docker-build-cpu docker-build-pytorch generate-openapi

PORT ?= 8000
REGISTRY ?= ghcr.io

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
	rm -f text-similarity-service-*.openapi.json

# The repo builds two images from one Dockerfile — they differ only in the
# SIMILARITY_PROFILE / INSTALL_MODEL build args. Tags (omit -service suffix):
#   text-similarity-cpu      (base, no PyTorch)
#   text-similarity-pytorch  (full, includes PyTorch-based algorithms)
docker-build-cpu:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=cpu \
		-t $(REGISTRY)/text-similarity-cpu .

docker-build-pytorch:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		-t $(REGISTRY)/text-similarity-pytorch .

docker-build: docker-build-cpu docker-build-pytorch

generate-openapi:
	python -m src.generate_openapi
