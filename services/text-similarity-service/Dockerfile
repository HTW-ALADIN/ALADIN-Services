# syntax=docker/dockerfile:1

# One repo builds two images:
#   text-similarity-cpu   — (default) no PyTorch, no pre-cached models
#   text-similarity-hf    — full PyTorch stack + all HF models pre-cached
# The profile is baked in as an ENV so the runtime catalog/spec only advertises
# what this image actually ships. The local ConceptNet Numberbatch model is NOT
# in any main image — it lives in the optional conceptnet-sidecar (see
# services/conceptnet-sidecar/, ADR-0001).
FROM python:3.12-slim AS builder
ARG SIMILARITY_PROFILE=cpu
ENV SIMILARITY_PROFILE=$SIMILARITY_PROFILE

# Model-based measures (HF) pull in PyTorch (~2.5 GB CUDA wheel). They are
# OPT-IN; the default cpu image stays small.
ARG INSTALL_MODEL=false
# German lexical relations (Odenet) — tiny, OPT-IN for all images.
ARG INSTALL_DE=false
# ONE switch that controls both the disk pre-cache (weights downloaded onto the
# image at build time) AND the RAM warm-start (loading at container start):
#   off  (default) — MODE 1 = cold. Nothing pre-downloaded, nothing warmed;
#                     everything lazy-loads (downloading if absent) per request.
#   all            — MODE 2 = warm. Every advertised HF model (SBERT MiniLM /
#                     MPNet / multilingual, cross-encoder stsb-roberta-base,
#                     bertscore roberta-large) is pre-downloaded to the image
#                     disk at build time AND loaded into RAM at startup.
#   measure:model[,measure:model...] — same, but only the selected models
#                     (partial): the rest are absent (lazy download at runtime).
# Baked in as ENV so a given image always ships and warms exactly what it
# advertises; no runtime config needed. Downloads land in a build-time HF cache
# dir that is COPY'd into the runtime cache, so a fresh "hf" container serves
# the first model request offline.
ARG HF_PRELOAD=off
ENV HF_PRELOAD=$HF_PRELOAD

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

# ── Optional: pre-cache the selected HF models at BUILD time ───────────────
# Only fetches/downloads the weights into a build-time HF cache dir; it does NOT
# import torch or load anything into RAM. Mirrors the runtime HF_HOME layout so
# sentence-transformers/transformers find them with no extra migration. The
# helper script itself gates on HF_PRELOAD (off = skip, all/partial = download
# the selection); this unconditional RUN keeps the Dockerfile parser simple.
ENV BUILT_HF=/app/built-hf
RUN mkdir -p $BUILT_HF && \
    HF_HOME=$BUILT_HF TRANSFORMERS_CACHE=$BUILT_HF python src/__precache_hf.py || \
    echo "WARN: HuggingFace pre-cache failed; models will download at runtime"

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

# Same preload profile as the build stage: baked in as ENV so a given image
# always warms exactly the advertised models, and no runtime config is needed.
ARG HF_PRELOAD=off
ENV HF_PRELOAD=$HF_PRELOAD

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
RUN chown -R 65534:65534 /var/text-similarity-cache

USER nobody

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
