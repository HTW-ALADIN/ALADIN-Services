# ── Stage 1: deps ────────────────────────────────────────────────────────────
# Installs all dependencies (dev deps needed to run tsx at runtime, since the
# service is served directly from TypeScript source, matching the repo's
# other Node/TypeScript services).
FROM node:22-slim AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM node:22-slim

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY tsconfig.json ./
COPY src/ ./src/

# ── Environment defaults ───────────────────────────────────────────────────────
# LLM_GATEWAY_BASE_URL / LLM_GATEWAY_API_KEY must be supplied at runtime and
# point at a self-hosted LLM Gateway instance's OpenAI-compatible API.
ENV NODE_ENV=production \
    PORT=8002 \
    HOST=0.0.0.0

# Run as the non-root `node` user baked into the base image rather than root.
RUN chown -R node:node /app
USER node

# ── Port ───────────────────────────────────────────────────────────────────────
EXPOSE 8002

# Default entrypoint runs the HTTP API. Override the command to invoke the
# CLI instead, e.g.:
#   docker run --rm <image> node_modules/.bin/tsx src/cli/index.ts generate - < request.json
CMD ["node_modules/.bin/tsx", "src/api/index.ts"]
