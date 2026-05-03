# ---- build stage ----
FROM python:3.12-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

COPY . /app
WORKDIR /app

# Sync into the project virtual environment; exclude dev dependencies
RUN uv sync --locked --no-dev

# ---- runtime stage ----
FROM python:3.12-slim-trixie

# Copy only the application code and the ready-made virtual environment
COPY --from=builder /app /app
WORKDIR /app

# Place the virtual-env Python first on PATH so we don't need `uv run`
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
