# Stage 1: Build
FROM rust:1.86-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config build-essential libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the dependency manifest first and build a throwaway binary
# against it, so the (slow) dependency-compilation layer is cached and only
# invalidated when Cargo.toml/Cargo.lock actually change — not on every
# source/README/test edit.
COPY Cargo.toml Cargo.lock ./
RUN mkdir src \
    && echo "fn main() {}" > src/main.rs \
    && echo "" > src/lib.rs \
    && cargo build --release \
    && rm -rf src

# Now copy the real source and rebuild — only this layer is invalidated by
# ordinary source changes.
COPY src ./src
RUN touch src/main.rs src/lib.rs && cargo build --release

# Stage 2: Runtime
FROM debian:bookworm-slim

# Install SSL libraries for runtime
RUN apt-get update && apt-get install -y --no-install-recommends libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary from the builder
COPY --from=builder /app/target/release/noise-generation-service /usr/local/bin/noise-generation-service

# Expose the HTTP port the server binds to by default
EXPOSE 8000

# Set the user
USER nobody

# Start the service (defaults to binding 0.0.0.0:8000)
CMD ["/usr/local/bin/noise-generation-service", "server"]
