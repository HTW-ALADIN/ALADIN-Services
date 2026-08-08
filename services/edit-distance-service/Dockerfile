# Stage 1: Build
#
# NOTE: pinned to 3.11 (not 3.12) because gmatch4py (below) unconditionally
# imports `numpy.distutils` on package import, and NumPy removed
# `numpy.distutils` entirely for Python >= 3.12 with no workaround.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the GED library gmatch4py (ged_hausdorff, ged_greedy, and the
# gmatch4py backend of ged_heuristic) *before* copying application source,
# so edits to src/ don't invalidate this expensive layer (git clone +
# Cython/C++ compile + its transitive deps). GMATCH4PY_REF/CYTHON_VERSION
# are the single source of truth shared with the Makefile and CI workflow
# (see gmatch4py.env) — only that file needs updating to bump either pin.
#
# - It has no PyPI release, so it is installed directly from GitHub,
#   pinned to a fixed commit for reproducibility (upstream has no
#   tags/releases). Note this still fetches and compiles unreviewed
#   third-party source at build/image time — see the README's "Graph
#   Backends" section for the supply-chain caveat and mitigation options.
# - Its setup.py imports numpy directly at build time (no pyproject.toml
#   build-system declared), so --no-build-isolation is required once numpy
#   is already present.
# - Its compiled extensions are built against the NumPy 1.x ABI (numpy<2 is
#   pinned in pyproject.toml) and unconditionally import `numpy.distutils`
#   on package import at runtime, which needs the *real* stdlib distutils
#   rather than setuptools' local shim (hence SETUPTOOLS_USE_DISTUTILS).
ENV SETUPTOOLS_USE_DISTUTILS=stdlib
COPY services/edit-distance-service/gmatch4py.env .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "numpy>=1.26.0,<2.0" && \
    . ./gmatch4py.env && \
    pip install --no-cache-dir "Cython==${CYTHON_VERSION}" && \
    pip install --no-cache-dir --no-build-isolation "gmatch4py @ ${GMATCH4PY_REF}"

# GEDLIB (gedlibpy, the "gedlib" backend of ged_astar/ged_heuristic) has no
# PyPI package and additionally requires the full GEDLIB C++ library
# (CMake, Boost, SWIG, ...) to build. It is intentionally not installed
# here; the service falls back gracefully at runtime when gedlibpy is
# unavailable (see src/graph/__init__.py _gedlib_compute).

COPY services/edit-distance-service/pyproject.toml .
COPY services/edit-distance-service/src/ src/

# Build/install the service wheel. numpy is already installed above at the
# version pyproject.toml requires, so this does not re-trigger the (now
# cached) gmatch4py layer.
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl && \
    rm -rf dist

# Stage 2: Runtime
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV SETUPTOOLS_USE_DISTUTILS=stdlib
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY services/edit-distance-service/src/ src/
COPY services/edit-distance-service/pyproject.toml .

# Set the user
USER nobody

# Start the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]