.PHONY: build test lint start clean compile-schemas generate-openapi docker-build smoke-test

prep:
	npm i

build:
	npm run build

test:
	npm run test

lint:
	npm run prettier
	npm run lint

start:
	docker compose up -d
	npm run dev

clean:
	rm -rf dist/ test/coverage/ test/results/ node_modules/

compile-schemas:
	npm run compile-schemas

generate-openapi:
	npm run generate:openapi

docker-build:
	docker build -t graph-rewriting-service .

smoke-test:
	./scripts/smoke-test.sh
