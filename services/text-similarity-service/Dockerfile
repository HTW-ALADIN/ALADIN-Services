# syntax=docker/dockerfile:1

# Stage 1: Build
FROM python:3.12-slim AS builder

# Model-based measures (sbert_cosine, cross_encoder, semantic_search via
# sentence-transformers, bertscore, embedding_cosine/wmd via gensim) pull in
# PyTorch (~2.5 GB CUDA wheel) and download models at runtime. They are
# therefore OPT-IN: the default image stays small (~100-150 MB of deps).
# Build with the full model stack using:
#   docker build --build-arg INSTALL_MODEL=true -t text-similarity-service .
ARG INSTALL_MODEL=false
# German lexical relations (Odenet via the `wn` library, `[de]` extra) are
# also OPT-IN and tiny (no PyTorch). Enable with:
#   docker build --build-arg INSTALL_DE=true -t text-similarity-service .
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

# Set the user
USER nobody

# Start the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]