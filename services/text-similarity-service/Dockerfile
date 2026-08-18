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
# The gensim ConceptNet Numberbatch model (~1.2 GB) is the DEFAULT backend for
# the `embedding_cosine` / `conceptnet_numberbatch` variant. It is normally
# downloaded on first use at runtime into the gensim cache dir. Setting
# PRECACHE_CONCEPTNET=true downloads it DURING the build (into the same gensim
# cache layout) so the first request is served immediately, offline. It does
# NOT pull in PyTorch — the model is pure gensim — but the ~1.2 GB layering is
# intentionally kept OPT-IN and wired to the heavyweight pytorch build so the
# default cpu image stays small:
#   docker build --build-arg SIMILARITY_PROFILE=pytorch \
#                --build-arg INSTALL_MODEL=true \
#                --build-arg PRECACHE_CONCEPTNET=true -t text-similarity-pytorch .
ARG PRECACHE_CONCEPTNET=false

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

# Pre-cache the gensim ConceptNet Numberbatch model (the default for the
# conceptnet_numberbatch variant) at BUILD time. We download to a stable path
# (return_path=True only fetches the .gz file — it does NOT load the model into
# RAM), which is then copied into the runtime cache dir. A download failure
# (offline build/image build farm) must not fail the whole image: the model is
# still fetched lazily at runtime on first use. Layout matches the runtime
# GENSIM_DATA_DIR so api.load() finds it with no extra migration.
ENV BUILT_GENSIM_DATA=/app/built-gensim-data
# The dir is ALWAYS created (possibly empty) so the later COPY never fails,
# whether or not pre-caching ran.
RUN if [ "$PRECACHE_CONCEPTNET" = "true" ]; then \
        mkdir -p $BUILT_GENSIM_DATA && \
        GENSIM_DATA_DIR=$BUILT_GENSIM_DATA python -c "import gensim.downloader as api; api.load('conceptnet-numberbatch-17-06-300', return_path=True)" \
        || echo "WARN: ConceptNet Numberbatch pre-cache failed; will download at runtime"; \
    else \
        mkdir -p $BUILT_GENSIM_DATA; \
    fi

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

# If the ConceptNet Numberbatch model was pre-cached during the build, seed the
# runtime gensim cache so the very first request is served offline. gensim.downloader
# creates no subdir when the download failed, so COPY only succeeds when present.
COPY --from=builder /app/built-gensim-data/. /var/text-similarity-cache/gensim-data/
RUN chown -R 65534:65534 /var/text-similarity-cache/gensim-data

# Set the user
USER nobody

# Start the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]