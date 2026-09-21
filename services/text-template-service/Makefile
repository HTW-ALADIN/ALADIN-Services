SERVICE := text-template-service
OPENAPI := openapi/openapi.yaml

.PHONY: prep build test coverage lint start clean docker-build generate-openapi docker-smoke

prep:
	cargo fetch --locked

build:
	cargo build --locked --release

test:
	cargo test --locked

coverage:
	./tests/check_coverage.sh

lint:
	cargo fmt --check
	cargo clippy --locked --all-targets --all-features -- -D warnings

start:
	cargo run --locked -- server

clean:
	cargo clean
	rm -f coverage.lcov

docker-build:
	docker build -t $(SERVICE) .

generate-openapi:
	cargo run --locked -- openapi --format yaml --output $(OPENAPI)

docker-smoke: docker-build
	./tests/docker_smoke.sh $(SERVICE)
