FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-fastapi \
        python3-graph-tool=2.91+ds-5 \
        python3-numpy \
        uvicorn \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY sidecar/src ./src

RUN groupadd --system appuser && useradd --system --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

ENV PYTHONPATH="/app/src"

USER appuser

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/healthz', timeout=3)"]

CMD ["uvicorn", "graph_tool_sidecar.main:app", "--host", "0.0.0.0", "--port", "8003"]
