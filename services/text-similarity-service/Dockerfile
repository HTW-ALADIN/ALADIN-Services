# syntax=docker/dockerfile:1

# One repo builds three images:
#   text-similarity-cpu            — (default) no PyTorch, no pre-cached models
#   text-similarity-hf             — full PyTorch stack + all HF models pre-cached,
#                                    but WITHOUT the local ConceptNet Numberbatch model
#                                    (SIMILARITY_DISABLE_LOCAL_CONCEPTNET=true)
#   text-similarity-conceptnet     — full PyTorch stack + HF models + the local
#                                    ConceptNet Numberbatch model pre-cached
# The profile is baked in as an ENV so the runtime catalog/spec only advertises
# what this image actually ships.
FROM python:3.12-slim AS builder
ARG SIMILARITY_PROFILE=cpu
ENV SIMILARITY_PROFILE=$SIMILARITY_PROFILE

# Model-based measures (HF) pull in PyTorch (~2.5 GB CUDA wheel) and optionally
# pre-download models at build time (PRECACHE_HF). They are OPT-IN; the default
# cpu image stays small.
ARG INSTALL_MODEL=false
# Pre-cache the HuggingFace models (SBERT MiniLM/MPNet/multilingual, cross-encoder
# stsb-roberta-base, bertscore roberta-large) at build time so a fresh "hf" or
# "conceptnet" container serves the first request offline. Downloads land in a
# build-time HF cache dir that is COPY'd into the runtime cache. A failure (e.g.
# offline build farm) must not fail the image: models remain lazy-downloaded at
# runtime if this step did not run.
ARG PRECACHE_HF=false
# Pre-cache the local gensim ConceptNet Numberbatch model (only for the
# "conceptnet" image). Downloads to a stable path (does NOT load it into RAM).
ARG PRECACHE_CONCEPTNET=false
# German lexical relations (Odenet) — tiny, OPT-IN for all images.
ARG INSTALL_DE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

# --mount=type=cache reuses pip downloads across builds (BuildKit), so the
# (optional) torch layer is only downloaded once.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    if [ "$INSTALL_MODEL" = "true" ]; then pip install --no-cache-dir -e ".[model]"; fi && \
    if [ "$INSTALL_DE" = "true" ]; then pip install --no-cache-dir -e ".[de]"; fi

# ── Optional: pre-cache the HuggingFace models at BUILD time ────────────────
# Only fetches/downloads the weights into a build-time HF cache dir; it does NOT
# import torch or load anything into RAM. Mirrors the runtime HF_HOME layout so
# sentence-transformers/transformers find them with no extra migration.
ENV BUILT_HF=/app/built-hf
# The helper script itself gates on PRECACHE_HF; this unconditional RUN keeps the
# Dockerfile parser simple (no nested python -c / if/then/fi confusion).
RUN mkdir -p $BUILT_HF && \
    HF_HOME=$BUILT_HF TRANSFORMERS_CACHE=$BUILT_HF PRECACHE_HF=$PRECACHE_HF python src/__precache_hf.py || \
    echo "WARN: HuggingFace pre-cache failed; models will download at runtime"

# ── Optional: pre-cache the gensim ConceptNet Numberbatch model at BUILD time ──
ENV BUILT_GENSIM_DATA=/app/built-gensim-data
RUN if [ "$PRECACHE_CONCEPTNET" = "true" ]; then \
        mkdir -p $BUILT_GENSIM_DATA && \
        GENSIM_DATA_DIR=$BUILT_GENSIM_DATA python -c "import gensim.downloader as api; api.load('conceptnet-numberbatch-17-06-300', return_path=True)" \
        || echo "WARN: ConceptNet Numberbatch pre-cache failed; will download at runtime"; \
    else \
        mkdir -p $BUILT_GENSIM_DATA; \
    fi

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY pyproject.toml .

ARG SIMILARITY_PROFILE=cpu
ENV SIMILARITY_PROFILE=$SIMILARITY_PROFILE

# Local ConceptNet model availability is baked in at build time: the "hf" image
# sets DISABLE_LOCAL_CONCEPTNET=true (keeps the runtime tiny and deterministic);
# the "conceptnet"/"pytorch" images leave it off.
ARG DISABLE_LOCAL_CONCEPTNET=false
ENV SIMILARITY_DISABLE_LOCAL_CONCEPTNET=$DISABLE_LOCAL_CONCEPTNET

# The service runs as `nobody`, whose default HOME (/nonexistent) is not
# writable. Runtime model/data downloads cache under `$HOME`, so point HOME at a
# writable dir and own it.
ENV HOME=/var/text-similarity-cache
ENV HF_HOME=/var/text-similarity-cache/hf \
    TRANSFORMERS_CACHE=/var/text-similarity-cache/hf/transformers \
    SENTENCE_TRANSFORMERS_HOME=/var/text-similarity-cache/hf/sentence-transformers \
    GENSIM_DATA_DIR=/var/text-similarity-cache/gensim-data \
    NLTK_DATA=/var/text-similarity-cache/nltk_data

RUN mkdir -p /var/text-similarity-cache && chown -R 65534:65534 /var/text-similarity-cache

# Seed the HF cache if it was built.
COPY --from=builder /app/built-hf/ /var/text-similarity-cache/hf/
# Seed the gensim cache if ConceptNet was pre-cached (harmless no-op otherwise).
COPY --from=builder /app/built-gensim-data/. /var/text-similarity-cache/gensim-data/
RUN chown -R 65534:65534 /var/text-similarity-cache

USER nobody

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
