# ---- build stage ----
FROM python:3.12-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

COPY . /app
WORKDIR /app

# Sync into the project virtual environment; exclude dev dependencies
RUN uv sync --locked --no-dev

# ---- runtime stage ----
FROM python:3.12-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy only the application code and the ready-made virtual environment
COPY --from=builder /app /app
WORKDIR /app

# Place the virtual-env Python first on PATH so we don't need `uv run`
ENV PATH="/app/.venv/bin:$PATH"

RUN groupadd --system appuser && useradd --system --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8004/health', timeout=3)"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004", "--app-dir", "src"]
