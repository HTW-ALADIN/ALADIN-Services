.PHONY: prep build test lint start clean docker-build generate-openapi dev prod smoke-test

prep:
	cargo fetch

build:
	cargo build --release

test:
	cargo test

lint:
	cargo fmt --check
	cargo clippy --all-targets --all-features -- -D warnings

start:
	cargo run

clean:
	rm -rf target/

docker-build:
	docker build -t noise-generation-service .

generate-openapi:
	cargo run -- openapi --output noise-generation-service.openapi.json

# Black-box smoke test against a *running* server (not run by `make test`).
# Usage: make start & then, in another shell, make smoke-test
smoke-test:
	./tests/test_all_algorithms.sh

dev:
	docker-compose -f docker-compose.dev.yml up --build

prod:
	docker-compose -f docker-compose.prod.yml up --build
