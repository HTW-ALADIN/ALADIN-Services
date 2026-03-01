# ── Stage 1: deps ────────────────────────────────────────────────────────────
# Installs all dependencies (dev deps needed to run tsx at runtime).
FROM node:22-slim AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# The API is served directly from TypeScript source via tsx (no separate
# compile step), which is the canonical start:api script in package.json.
FROM node:22-slim

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY tsconfig.json ./
COPY src/ ./src/

# ── Environment defaults ───────────────────────────────────────────────────────
ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

# ── Port ───────────────────────────────────────────────────────────────────────
# Defaultport: 3000 – Fastify HTTP API
EXPOSE 3000

CMD ["node_modules/.bin/tsx", "src/api/index.ts"]
