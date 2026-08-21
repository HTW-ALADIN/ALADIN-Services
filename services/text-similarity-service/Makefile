.PHONY: prep build test lint start clean \
        docker-build docker-build-cpu docker-build-pytorch docker-build-hf \
        generate-openapi

PORT ?= 8000
REGISTRY ?= ghcr.io
# Warm-start preload profile baked into the image: off (default/cold), all,
# or a partial measure:model[,measure:model...] list (see Dockerfile).
HF_PRELOAD ?= off

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
# SIMILARITY_PROFILE / INSTALL_MODEL / PRECACHE_HF / HF_PRELOAD build args.
#   text-similarity-cpu            (base, no PyTorch, no models pre-cached)
#   text-similarity-hf/pytorch     (full — PyTorch + all HF models pre-cached)
# Warm-start profile (HF_PRELOAD): off (default/cold), all, or a partial
# measure:model[,measure:model...] list. Examples:
#   make docker-build-hf HF_PRELOAD=all                       # warm everything
#   make docker-build-hf HF_PRELOAD="sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large"  # partial lazy
# The local ConceptNet Numberbatch model is NOT in any main image: it is served
# by the optional conceptnet-sidecar (see services/conceptnet-sidecar/).
docker-build-cpu:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=cpu \
		-t $(REGISTRY)/text-similarity-cpu .

# hf and pytorch are the SAME full build now (the conceptnet pre-cache is gone);
# the legacy "pytorch" name is kept as a tag alias so existing deployments work.
docker-build-hf:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		--build-arg PRECACHE_HF=true \
		--build-arg HF_PRELOAD=$(HF_PRELOAD) \
		-t $(REGISTRY)/text-similarity-hf \
		-t $(REGISTRY)/text-similarity-pytorch .

docker-build-pytorch: docker-build-hf

docker-build: docker-build-cpu docker-build-hf

generate-openapi:
	python -m src.generate_openapi
