# Stage 1: Build
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libpython3.12-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/edit-distance-service/pyproject.toml .
COPY services/edit-distance-service/src/ src/

# Install base dependencies and build wheel
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl && \
    rm -rf dist

# Install optional GED library (gedlibpy) from monorepo third_party/
# (not on PyPI — ships with the ALADIN monorepo)
COPY third_party/gedlibpy/ /tmp/third_party/gedlibpy/
RUN pip install --no-cache-dir Cython && \
    cd /tmp/third_party/gedlibpy && \
    python setup.py build_ext --inplace && \
    pip install --no-cache-dir . && \
    rm -rf /tmp/third_party

# Install optional GED library (gmatch4py) from PyPI
# (ged_hausdorff, ged_greedy, ged_heuristic backends)
RUN pip install --no-cache-dir gmatch4py

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/edit-distance-service/src/ src/
COPY services/edit-distance-service/pyproject.toml .

# Set the user
USER nobody

# Start the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]