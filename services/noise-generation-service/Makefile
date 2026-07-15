.PHONY: build build-local run test lint clean dev prod

build:
	docker build -t noise-generation-service .

build-local:
	cargo build --release

run:
	docker run -p 8000:8000 noise-generation-service

dev:
	docker-compose -f docker-compose.dev.yml up --build

prod:
	docker-compose -f docker-compose.prod.yml up --build

test:
	cargo test

clean:
	rm -rf target/