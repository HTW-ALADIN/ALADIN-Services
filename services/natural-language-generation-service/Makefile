IMAGE_NAME  := natural-language-generation-service
PORT        ?= 8000

.PHONY: prep build test coverage lint start clean docker-build docker-smoke generate-openapi

prep:
	npm ci

build:
	npm run build

test:
	npm run test:coverage

coverage:
	npm run test:coverage

lint:
	npm run lint
	npm run format:check

start:
	PORT=$(PORT) npm run start:dev

clean:
	rm -rf coverage dist node_modules

docker-build:
	docker build -t $(IMAGE_NAME) .

docker-smoke: docker-build
	./test/docker-smoke.sh $(IMAGE_NAME)

generate-openapi:
	npm run generate:openapi
