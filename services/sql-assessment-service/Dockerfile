FROM node:20

WORKDIR /app

COPY package.json ./
COPY tsconfig.json ./

RUN npm install

COPY ./ ./

# RUN npx ts-node src/index.ts
EXPOSE 3333

CMD ["npx", "ts-node", "src/index.ts"]
