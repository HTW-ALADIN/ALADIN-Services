FROM sagemath/sagemath:10.4

# The base image already runs as 'sage' user (uid=1001).
# Switch to root for build steps that need it.
USER root

RUN mkdir -p /app && chown sage:sage /app

WORKDIR /app

# Copy source code, config, lock file and registry YAMLs
COPY pyproject.toml uv.lock .
COPY src/ src/
COPY registry/ registry/

# Resolve exact, pinned runtime dependency versions from uv.lock (no test
# deps in production image) so the published image is reproducible, then
# install them with sage's own pip. `uv` itself is only a build-time tool
# and is not installed into the image's runtime environment.
# SAGE_MAX_MEMORY_MB and SAGE_MAX_CONCURRENCY are tuned for the 2 GB RAM
# minimum deployment target (see README.md). SAGE_CONTAINER_MEMORY_MB is
# set to a safe estimate so the startup sanity check in executor.py passes.
ENV SAGE_MAX_MEMORY_MB=2048 \
    SAGE_MAX_CONCURRENCY=2 \
    SAGE_MAX_PROCESSES=512 \
    SAGE_CONTAINER_MEMORY_MB=4096
RUN sage -python -m pip install --no-cache-dir uv \
    && sage -python -m uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.lock.txt \
    && sage -python -m pip install --no-cache-dir -r /tmp/requirements.lock.txt \
    && sage -python -m pip install --no-cache-dir --no-deps -e "." \
    && sage -python -m pip uninstall --yes uv \
    && rm -f /tmp/requirements.lock.txt \
    && rm -rf /root/.cache /home/sage/.cache /tmp/*

# Rebuild cysignals from source to avoid mmap issues (WSL2 / Docker known problem)
# The prebuilt cysignals .so fails to map segment from shared object in containers.
RUN sage -python -m pip install --force-reinstall --no-cache-dir --no-binary=cysignals cysignals \
    && rm -rf /home/sage/.cache /tmp/*

# Install curl for health check (not available in sagemath base image)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=2 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

USER sage

CMD ["sage", "-python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]