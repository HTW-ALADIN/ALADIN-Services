# Stage 1: Build
FROM rust:1.86-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y pkg-config build-essential libssl-dev

WORKDIR /app
COPY . .

# Compile the project
RUN cargo build --release

# Stage 2: Runtime
FROM debian:bookworm-slim

# Install SSL libraries for runtime
RUN apt-get update && apt-get install -y libssl3

# Copy the binary from the builder
COPY --from=builder /app/target/release/noise-generation-service /usr/local/bin/noise-generation-service

# Set the user
USER nobody

# Start the service
CMD ["/usr/local/bin/noise-generation-service"]
