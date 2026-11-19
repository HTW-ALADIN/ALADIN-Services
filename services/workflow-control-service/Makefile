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
	npm start

clean:
	rm -rf build/ node_modules/

docker-build:
	docker build -t workflow-control-service .

generate-openapi:
	npm run generate:openapi