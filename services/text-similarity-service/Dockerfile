# syntax=docker/dockerfile:1

# Stage 1: Build
FROM python:3.12-slim AS builder

# One repo builds two images that differ only in the PyTorch-based measures:
#   text-similarity-cpu      — (default) SIMILARITY_PROFILE=cpu, INSTALL_MODEL=false (base, no PyTorch)
#   text-similarity-pytorch  — SIMILARITY_PROFILE=pytorch, INSTALL_MODEL=true (full stack)
# The cpu image is the default build. The profile is baked in as an ENV so the
# runtime catalog/spec only advertises what this image actually ships.
ARG SIMILARITY_PROFILE=cpu
ENV SIMILARITY_PROFILE=$SIMILARITY_PROFILE

# Model-based measures (sbert_cosine, cross_encoder, semantic_search via
# sentence-transformers, bertscore) pull in PyTorch (~2.5 GB CUDA wheel) and
# download models at runtime. They are OPT-IN; the default cpu image stays
# small. Build the full model stack with:
#   docker build --build-arg SIMILARITY_PROFILE=pytorch --build-arg INSTALL_MODEL=true -t text-similarity-pytorch .
ARG INSTALL_MODEL=false
# German lexical relations (Odenet via the `wn` library, `[de]` extra) are
# tiny (no PyTorch) and OPT-IN for both images:
#   docker build --build-arg INSTALL_DE=true -t text-similarity-cpu .
# The Odenet data itself is downloaded at runtime (never baked into the image).
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
# (optional) torch layer is only downloaded once. Without INSTALL_MODEL the
# light dependency set is installed in seconds.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    if [ "$INSTALL_MODEL" = "true" ]; then pip install --no-cache-dir -e ".[model]"; fi && \
    if [ "$INSTALL_DE" = "true" ]; then pip install --no-cache-dir -e ".[de]"; fi

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY pyproject.toml .

# Carry the build-time profile into the running service (cpu by default).
ARG SIMILARITY_PROFILE=cpu
ENV SIMILARITY_PROFILE=$SIMILARITY_PROFILE

# The service runs as `nobody`, whose default HOME (/nonexistent) is not
# writable. Runtime model/data downloads (HuggingFace, gensim, NLTK, Odenet)
# cache under `$HOME`, so point HOME at a directory the app user can write to
# and own it. Without this the pytorch image's first model request fails with
# `Permission denied` on the cache dir.
ENV HOME=/var/text-similarity-cache
# Point the downloaders' caches there explicitly (belt and braces; they default
# to $HOME anyway) so a single volume can be mounted to pre-cache models.
ENV HF_HOME=/var/text-similarity-cache/hf \
    TRANSFORMERS_CACHE=/var/text-similarity-cache/hf/transformers \
    SENTENCE_TRANSFORMERS_HOME=/var/text-similarity-cache/hf/sentence-transformers \
    GENSIM_DATA_DIR=/var/text-similarity-cache/gensim-data \
    NLTK_DATA=/var/text-similarity-cache/nltk_data

# Create the cache dir and give the app user write access.
RUN mkdir -p /var/text-similarity-cache && chown -R 65534:65534 /var/text-similarity-cache

# Set the user
USER nobody

# Start the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]