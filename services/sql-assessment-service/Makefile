.PHONY: prep build test lint start clean docker-build generate-openapi cli

prep:
	npm ci

build:
	npm run build

test:
	npm run test

lint:
	npm run lint

start:
	docker compose up -d
	npm run dev

clean:
	rm -rf build/

docker-build:
	docker build -t sql-assessment-service .

generate-openapi:
	npm run generate-openapi

cli:
	npm run build
	@echo "CLI ready: node build/cli/index.js --help"
