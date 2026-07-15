.PHONY: build build-local run test lint clean

build:
	docker build -t noise-generation-service .

build-local:
	cargo build --release

run:
	docker run -p 3000:3000 noise-generation-service

test:
	docker run --rm -v $(PWD):/app -w /app rust:1.80-slim-bookworm cargo test --manifest-path /app/services/noise-generation-service/Cargo.toml

lint:
	docker run --rm -v $(PWD):/app -w /app rust:1.80-slim-bookworm cargo clippy --manifest-path /app/services/noise-generation-service/Cargo.toml --all-targets --all-features -- -D warnings

clean:
	docker rmi noise-generation-service
	cargo clean
