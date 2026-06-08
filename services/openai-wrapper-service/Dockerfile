FROM python:3.12-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

COPY . /app
WORKDIR /app
RUN uv sync --locked --no-dev

EXPOSE 8002

CMD ["uv", "run", "--no-sync", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8002", "--app-dir", "src"]
