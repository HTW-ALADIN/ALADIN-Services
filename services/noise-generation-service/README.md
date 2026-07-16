# Noise Generation Service

A unified REST API for noise generation libraries, supporting multiple noise algorithms and backends.

## Prerequisites

This repository contains all files necessary to run the application in local development and production environments.
It requires Docker and Rust 1.80+ on your system.

When cloning this repository and opening it through VSCode, it will ask you to install all recommended VSCode extensions.

## Getting started

In order to install and run this application in your local development environment, you first need to install all dependencies via cargo:

```bash
cargo build
```

## Overview

The Noise Generation Service provides a standardized REST API for generating various types of noise, including Perlin, Simplex, and other advanced noise algorithms. It supports multiple backend implementations for optimal performance and compatibility.

## Features

- Multiple noise algorithms support
- Flexible backend selection
- Standardized REST API
- Docker-ready deployment
- Comprehensive test coverage
- CLI interface

## API Endpoints

### List Algorithms
- **Endpoint**: `GET /v1/algorithms`
- **Description**: Lists all available algorithm/backend combinations
- **Response**: Array of algorithm objects with backend information

### Generate Noise
- **Endpoint**: `POST /v1/noise`
- **Description**: Generates noise based on the specified algorithm and backend
- **Request Body**:
  - `algorithm`: The noise generation algorithm to use
  - `backend`: The backend implementation to use
  - `params`: Algorithm-specific parameters
  - `sampling`: Sampling configuration
  - `output`: Output format configuration
- **Responses**:
  - `201`: Noise field created
  - `202`: Noise field generation accepted

### Retrieve Noise Field
- **Endpoint**: `GET /v1/noise/{fieldId}`
- **Description**: Retrieves a generated noise field by its ID
- **Parameters**:
  - `fieldId`: The ID of the noise field to retrieve
- **Response**: Noise field data

### Retrieve Noise Point
- **Endpoint**: `GET /v1/noise/{fieldId}/point`
- **Description**: Retrieves a specific noise value at (x, y) coordinates
- **Parameters**:
  - `fieldId`: The ID of the noise field
  - `x`: X coordinate
  - `y`: Y coordinate
- **Response**: Noise value (float)

## Algorithms and Backends

The service supports 14 noise algorithm families with specific backend support:

| Algorithm | Canonical Name | Family | Backend Support | Underlying Function |
|-----------|----------------|--------|-----------------|---------------------|
| `perlin` | Perlin noise | Perlin | `fastnoise_lite`, `noise_rs` | `SetNoiseType(Perlin)` + `GetNoise(x, y[, z])` / `Perlin::new(seed).get([x, y])` |
| `simplex` | Simplex noise (classic) | Simplex | `noise_rs` only | `Simplex::new(seed).get(point)` |
| `opensimplex2` | OpenSimplex2 / OpenSimplex2S | OpenSimplex | `fastnoise_lite` (default) | `SetNoiseType(OpenSimplex2 | OpenSimplex2S)` + `GetNoise(x, y[, z])` |
| `supersimplex` | SuperSimplex | SuperSimplex | `noise_rs` only | `SuperSimplex::new(seed).get(point)` |
| `value` | Value noise (+cubic) | Value | `fastnoise_lite` (default) | `SetNoiseType(Value | ValueCubic)` + `GetNoise(x, y[, z])` |
| `cellular` | Cellular / Worley / Voronoi | Cellular | `fastnoise_lite` (default) | `SetNoiseType(Cellular)`, `SetCellularDistanceFunction(...)`, `SetCellularReturnType(...)`, `SetCellularJitter(...)` + `GetNoise(x, y[, z])` |
| `fbm` | Fractal Brownian Motion | Fractal | `fastnoise_lite` (default) | `SetFractalType(FBm)`, `SetFractalOctaves(octaves)`, `SetFractalLacunarity(lacunarity)`, `SetFractalGain(gain)` |
| `billow` | Billow noise | Fractal | `noise_rs` only | `Billow::new(seed).set_octaves(octaves).set_persistence(persistence)` |
| `ridged_multi` | Ridged multifractal | Fractal | `fastnoise_lite` (default) | `SetFractalType(Ridged)`, `SetFractalOctaves(octaves)`, `SetFractalLacunarity(lacunarity)`, `SetFractalGain(gain)` |
| `hybrid_multi` | HybridMulti fractal | Fractal | `noise_rs` only | `HybridMulti::new(seed).set_octaves(octaves).set_persistence(persistence)` |
| `pingpong` | PingPong fractal | Fractal | `fastnoise_lite` only | `SetFractalType(PingPong)`, `SetFractalPingPongStrength(strength)` |
| `domain_warp` | Domain warping | Transform | `fastnoise_lite` only | `SetDomainWarpType(warp_type)`, `SetDomainWarpAmp(amplitude)` + `DomainWarp2D/3D(x, y[, z])` |
| `combinator` | Generic combinators | Combinator | `noise_rs` only | `Add`/`Multiply`/`Min`/`Max`/`Blend`/`Turbulence`/`ScalePoint` (selected via `op` sub-field, wrapping `source1`, `source2`) |
| `utility` | Utility / deterministic generators | Utility | `noise_rs` only | `Constant::new(value)` / `Cylinders::new()` (selected via `kind` sub-field) |
| `white` | White noise | Native | `native` | `seeded_prng(seed, x, y, z, w).next_f32() * 2.0 - 1.0` — uncorrelated per-cell/per-point noise, no interpolation |

## Usage

### Basic Usage

```bash
# List available algorithms
curl -X GET http://localhost:8000/v1/algorithms

# Generate Perlin noise
curl -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "perlin",
    "backend": "fastnoise_lite",
    "params": {},
    "sampling": {
      "mode": "grid",
      "dimensions": 2
    },
    "output": {
      "format": "json",
      "normalize": "none"
    }
  }'

# Retrieve noise field
curl -X GET http://localhost:8000/v1/noise/nsf_123
```

### Using the CLI

```bash
# Generate noise using CLI
cargo run -- generate --algorithm perlin --backend fastnoise_lite
```

## Testing

### Unit Tests

```bash
cargo test
```

### Integration Tests

```bash
cd tests && cargo test
```

## Deployment

### Development Environment

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build
```

### Production Environment (Docker + Compose)

```bash
# Start production environment
docker-compose -f docker-compose.prod.yml up -d
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License.
