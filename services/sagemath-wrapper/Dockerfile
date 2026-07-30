FROM sagemath/sagemath:latest

# Create non-root user
RUN useradd --create-home --shell /bin/bash sageuser \
    && mkdir -p /app && chown sageuser:sageuser /app

WORKDIR /app

# Install Python runtime dependencies (no test deps in production image)
COPY pyproject.toml .
RUN sage -python -m pip install --no-cache-dir -e "." \
    && rm -rf /root/.cache /tmp/*

# Copy service code
COPY src/ src/

# Health check: curl is available in the base image
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

USER sageuser

CMD ["sage", "-python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]