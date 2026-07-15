# Stage 1: Build
FROM rust:1.80-slim-bookworm AS builder

# Installiere Build-Abhängigkeiten
RUN apt-get update && apt-get install -y pkg-config build-essential libssl-dev

WORKDIR /app
COPY . .

# Kompiliere das Projekt
RUN cargo build --release

# Stage 2: Runtime
FROM debian:bookworm-slim

# Installiere SSL-Bibliotheken für die Laufzeit
RUN apt-get update && apt-get install -y libssl3

# Kopiere das Binary aus dem Builder
COPY --from=builder /app/target/release/noise-generation-service /usr/local/bin/noise-generation-service

# Legt den Benutzer fest
USER nobody

# Starte den Service
CMD ["/usr/local/bin/noise-generation-service"]

# Starte den Service
CMD ["noise-generation-service"]
