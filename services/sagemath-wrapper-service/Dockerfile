FROM sagemath/sagemath:latest

# The base image already runs as 'sage' user (uid=1001).
# Switch to root for build steps that need it.
USER root

RUN mkdir -p /app && chown sage:sage /app

WORKDIR /app

# Copy source code, config, and registry YAMLs
COPY pyproject.toml .
COPY src/ src/
COPY registry/ registry/

# Install Python runtime dependencies (no test deps in production image)
RUN sage -python -m pip install --no-cache-dir -e "." \
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