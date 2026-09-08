FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-fastapi \
        python3-graph-tool \
        python3-numpy \
        uvicorn \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY sidecar/src ./src

ENV PYTHONPATH="/app/src"

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/healthz', timeout=3)"]

CMD ["uvicorn", "graph_tool_sidecar.main:app", "--host", "0.0.0.0", "--port", "8003"]
