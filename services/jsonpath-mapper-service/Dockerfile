# ── Stage 1: build ───────────────────────────────────────────────────────────
# Install all deps (incl. devDeps for esbuild) and bundle the API.
FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN node scripts/build-api.mjs

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Alpine base + single bundled file — no node_modules needed.
FROM node:22-alpine

WORKDIR /app

COPY --from=build /app/dist/ ./

# ── Environment defaults ───────────────────────────────────────────────────────
ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

# ── Port ───────────────────────────────────────────────────────────────────────
# Defaultport: 3000 – Fastify HTTP API
EXPOSE 3000

CMD ["node", "api.cjs"]
