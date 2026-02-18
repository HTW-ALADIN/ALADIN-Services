# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Compiles TypeScript to JavaScript and installs production-only dependencies.
FROM node:22-slim AS builder

WORKDIR /build

# Install dependencies first (separate layer for better cache reuse)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and compile
COPY tsconfig.json ./
COPY src/ ./src/
RUN npm run build

# Prune to production deps only
RUN npm ci --omit=dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Uses the official Neo4j image as base so Neo4j is available out of the box.
# Node 22 is installed via NodeSource.
FROM neo4j:5.25.1

# Install Node.js 22 (NodeSource) and supervisord
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates supervisor && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy compiled app and production node_modules from builder
WORKDIR /app
COPY --from=builder /build/dist ./dist
COPY --from=builder /build/node_modules ./node_modules

# Copy process manager config and entrypoint
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create log directory for supervisord
RUN mkdir -p /var/log/supervisor

# ── Environment defaults ───────────────────────────────────────────────────────
# NEO4J_AUTH is constructed in entrypoint.sh from USERNAME + PASSWORD.
# NEO4J_PASSWORD has a default, but should be supplied at runtime.
ENV APP_ENV=production \
    NEO4J_URI=bolt://localhost:7687 \
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=graph_rewriting


# ── Ports ──────────────────────────────────────────────────────────────────────
# 8080  – Fastify HTTP API
# 7474  – Neo4j Browser UI
# 7687  – Neo4j Bolt
EXPOSE 8080 7474 7687

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
