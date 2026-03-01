.PHONY: prep build test lint start clean docker-build generate-openapi

prep:
	npm ci

build:
	npm run build

test:
	npm run test

lint:
	npm run lint

start:
	npm run start:api

clean:
	rm -rf dist/ .nyc_output/ coverage/ node_modules/

docker-build:
	docker build -t jsonpath-mapper-service .

generate-openapi:
	npm run generate:openapi
