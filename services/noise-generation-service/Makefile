.PHONY: prep build test lint start clean docker-build generate-openapi dev prod

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

dev:
	docker-compose -f docker-compose.dev.yml up --build

prod:
	docker-compose -f docker-compose.prod.yml up --build
