FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src

RUN npm run build

FROM node:22-alpine

WORKDIR /app

COPY --from=build /app/build ./build

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

USER node

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health').then((r)=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

EXPOSE 3000

CMD ["node", "build/server.js"]