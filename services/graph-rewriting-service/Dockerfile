# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Bundles TypeScript to JavaScript via esbuild.
FROM node:22-slim AS builder

WORKDIR /build

# Install dependencies first (separate layer for better cache reuse)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY tsconfig.json ./
COPY scripts/ ./scripts/
COPY src/ ./src/
RUN npm run build

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# @grafeo-db/js ships a native Rust addon compiled against glibc (gnu).
# Using node:22-slim (Debian/glibc) keeps the same libc as the builder so the
# native binding works.  node:22-alpine (musl) would require the -musl variant.
FROM node:22-slim

WORKDIR /app

# Copy bundled app output from builder
COPY --from=builder /build/dist ./dist

# @grafeo-db/js ships a native Rust addon (.node file) that cannot be bundled
# by esbuild and is therefore externalized.  Copy the packages so both the
# in-memory and neo4j backends are available at runtime.
COPY --from=builder /build/node_modules/@grafeo-db ./node_modules/@grafeo-db

# ── Environment defaults ───────────────────────────────────────────────────────
# DB_BACKEND defaults to "memory" (no external DB needed).
# Set DB_BACKEND=neo4j to use Neo4j and supply all three NEO4J_* vars;
# NEO4J_PASSWORD has no default and must be provided explicitly.
ENV APP_ENV=production \
    NODE_ENV=production \
    NEO4J_URI=bolt://neo4j:7687 \
    NEO4J_USERNAME=neo4j

# ── Port ────────────────────────────────────────────────────────────────────────
# 8080  – Fastify HTTP API
EXPOSE 8080

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:8080/health', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

# CLI is also available inside the container:
#   docker run --rm -e NEO4J_URI=... graph-rewriting-service node dist/cli.js transform /data/request.json

# Start API server by default
CMD ["node", "dist/index.js"]
