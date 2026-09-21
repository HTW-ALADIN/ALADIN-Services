FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# The model is mounted or COPY'd in at runtime via CONCEPTNET_MODEL_PATH; it is
# deliberately NOT baked in (lazy-load + TTL keeps the image and idle RAM small).
ENV HOME=/var/conceptnet-cache
RUN mkdir -p /var/conceptnet-cache && chown -R 65534:65534 /var/conceptnet-cache

USER nobody

EXPOSE 8200

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8200"]
