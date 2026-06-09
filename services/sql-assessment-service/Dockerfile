# ---- build stage ----
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY src/ src/
COPY tsconfig.json import-meta-url.js ./

RUN npm run build

# Install only production deps for the runtime image.
# @electric-sql/pglite is excluded from the bundle (WASM cannot be inlined).
# swagger-ui-dist is excluded because it serves static files from the filesystem.
RUN npm ci --omit=dev

# ---- production stage ----
FROM node:20-alpine

WORKDIR /app

COPY --from=build /app/build/ ./build/
COPY --from=build /app/node_modules/@electric-sql/pglite ./node_modules/@electric-sql/pglite
COPY --from=build /app/node_modules/swagger-ui-dist ./node_modules/swagger-ui-dist

EXPOSE 3000

CMD ["node", "build/index.js"]
