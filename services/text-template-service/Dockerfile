FROM rust:1.86-slim-bookworm AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src \
    && printf 'fn main() {}\n' > src/main.rs \
    && printf '\n' > src/lib.rs \
    && cargo build --locked --release \
    && rm -rf src

COPY src ./src
RUN touch src/main.rs src/lib.rs && cargo build --locked --release

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/text-template-service /usr/local/bin/text-template-service

USER nobody
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/healthz >/dev/null || exit 1
ENTRYPOINT ["/usr/local/bin/text-template-service"]
CMD ["server"]
