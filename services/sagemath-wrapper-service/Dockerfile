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
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.lock.txt \
    && sage -python -m pip install --no-cache-dir -r /tmp/requirements.lock.txt \
    && sage -python -m pip install --no-cache-dir --no-deps -e "." \
    && pip uninstall --yes uv \
    && rm -f /tmp/requirements.lock.txt \
    && rm -rf /root/.cache /home/sage/.cache /tmp/*

# Rebuild cysignals from source to avoid mmap issues (WSL2 / Docker known problem)
# The prebuilt cysignals .so fails to map segment from shared object in containers.
RUN sage -python -m pip install --force-reinstall --no-cache-dir --no-binary=cysignals cysignals \
    && rm -rf /home/sage/.cache /tmp/*

# Health check: curl is available in the base image
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

USER sage

CMD ["sage", "-python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]