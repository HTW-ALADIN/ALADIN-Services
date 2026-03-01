FROM node:20

WORKDIR /app

COPY package.json ./
COPY tsconfig.json ./

RUN npm install

COPY ./ ./

EXPOSE 3333

CMD ["npx", "ts-node", "src/index.ts"]
