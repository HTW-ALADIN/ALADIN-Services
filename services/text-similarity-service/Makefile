.PHONY: prep build test lint start clean \
        docker-build docker-build-cpu docker-build-pytorch docker-build-hf \
        generate-openapi

PORT ?= 8000
REGISTRY ?= ghcr.io
# HF_PRELOAD controls BOTH sides of the HF models: which weights are
# pre-downloaded onto the image disk (build time) AND warmed into RAM at
# container start. off (default) = cold start, all = warm start, or a partial
# measure:model[,measure:model...] list (see Dockerfile).
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
# SIMILARITY_PROFILE / INSTALL_MODEL / HF_PRELOAD build args.
#   text-similarity-cpu            (base, no PyTorch, no model disk/RAM preload)
#   text-similarity-hf/pytorch     (full — PyTorch; disk+RAM preload per HF_PRELOAD)
# HF_PRELOAD: off (default/cold), all, or a partial measure:model[,...] list.
# Examples:
#   make docker-build-hf HF_PRELOAD=off      # cold: disk empty, boot ~1s, 1st request lazy
#   make docker-build-hf HF_PRELOAD=all      # warm: disk+RAM filled, 1st request in ms
#   make docker-build-hf HF_PRELOAD="sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large"  # partial
# The local ConceptNet Numberbatch model is NOT in any main image: it is served
# by the optional conceptnet-sidecar (see services/conceptnet-sidecar/).
docker-build-cpu:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=cpu \
		--build-arg HF_PRELOAD=off \
		-t $(REGISTRY)/text-similarity-cpu .

# hf and pytorch are the SAME full build now (the conceptnet pre-cache is gone);
# the legacy "pytorch" name is kept as a tag alias so existing deployments work.
docker-build-hf:
	docker build -f Dockerfile \
		--build-arg SIMILARITY_PROFILE=pytorch \
		--build-arg INSTALL_MODEL=true \
		--build-arg HF_PRELOAD=$(HF_PRELOAD) \
		-t $(REGISTRY)/text-similarity-hf \
		-t $(REGISTRY)/text-similarity-pytorch .

docker-build-pytorch: docker-build-hf

docker-build: docker-build-cpu docker-build-hf

generate-openapi:
	python -m src.generate_openapi
