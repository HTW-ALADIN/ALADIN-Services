.PHONY: prep build test lint start clean \
        docker-build docker-build-cpu docker-build-pytorch docker-build-hf docker-build-conceptnet \
        generate-openapi

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

# The repo builds images from one Dockerfile — they differ only in the
# SIMILARITY_PROFILE / INSTALL_MODEL / PRECACHE_* / DISABLE_LOCAL_CONCEPTNET
# build args.
#   text-similarity-cpu       (base, no PyTorch, no models pre-cached)
#   text-similarity-pytorch   (full — includes PyTorch + ConceptNet pre-cached)
#   text-similarity-hf        (PyTorch + all HF models, NO local ConceptNet)
#   text-similarity-conceptnet(PyTorch + HF + local ConceptNet pre-cached)
docker-build-cpu:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=cpu \
		-t $(REGISTRY)/text-similarity-cpu .

docker-build-pytorch:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		--build-arg PRECACHE_HF=true \
		--build-arg PRECACHE_CONCEPTNET=true \
		-t $(REGISTRY)/text-similarity-pytorch .

docker-build-hf:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		--build-arg PRECACHE_HF=true \
		--build-arg DISABLE_LOCAL_CONCEPTNET=true \
		-t $(REGISTRY)/text-similarity-hf .

docker-build-conceptnet:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		--build-arg PRECACHE_HF=true \
		--build-arg PRECACHE_CONCEPTNET=true \
		-t $(REGISTRY)/text-similarity-conceptnet .

docker-build: docker-build-cpu docker-build-pytorch docker-build-hf docker-build-conceptnet

generate-openapi:
	python -m src.generate_openapi
