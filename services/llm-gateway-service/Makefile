IMAGE_NAME  := llm-gateway-service
OPENAPI_OUT := llm-gateway-service.openapi.json
PORT        ?= 8002

.PHONY: prep build test lint start clean docker-build generate-openapi

prep:
	npm ci

build:
	npm run build

test:
	npm run test:coverage

lint:
	npm run lint
	npx prettier --check .

start:
	PORT=$(PORT) npm run start:api

clean:
	rm -rf dist/ coverage/ node_modules/ $(OPENAPI_OUT)

docker-build:
	docker build -t $(IMAGE_NAME) .

generate-openapi:
	npm run generate:openapi
