# Noise Generation Service

A unified REST API for noise generation libraries, supporting multiple noise algorithms and backends.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [Algorithms](#algorithms)
- [Usage](#usage)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)

## Overview

The Noise Generation Service provides a standardized REST API for generating various types of noise, including Perlin, Simplex, and other advanced noise algorithms. It supports multiple backend implementations for optimal performance and compatibility.

## Features

- Multiple noise algorithms support
- Flexible backend selection
- Standardized REST API
- Docker-ready deployment
- Comprehensive test coverage

## API Endpoints

### 1. List Algorithms
- **Endpoint**: `GET /v1/algorithms`
- **Description**: Lists all available algorithm/backend combinations
- **Response**: Array of algorithm objects with backend information

### 2. Generate Noise
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

### 3. Retrieve Noise Field
- **Endpoint**: `GET /v1/noise/{fieldId}`
- **Description**: Retrieves a generated noise field by its ID
- **Parameters**:
  - `fieldId`: The ID of the noise field to retrieve
- **Response**: Noise field data

## Algorithms

The service supports the following noise algorithms:

| Algorithm | Description | Backend Support |
|-----------|-------------|-----------------|
| `perlin` | Perlin noise | `fastnoise_lite`, `noise_rs` |
| `simplex` | Simplex noise (classic) | `fastnoise_lite`, `noise_rs` |
| `opensimplex2` | OpenSimplex2 / OpenSimplex2S | `fastnoise_lite`, `noise_rs` |
| `supersimplex` | SuperSimplex | `fastnoise_lite`, `noise_rs` |
| `value` | Value noise (+cubic) | `fastnoise_lite`, `noise_rs` |
| `cellular` | Cellular / Worley / Voronoi | `fastnoise_lite`, `noise_rs` |
| `fbm` | Fractal Brownian Motion | `fastnoise_lite`, `noise_rs` |
| `billow` | Billow noise | `fastnoise_lite`, `noise_rs` |
| `ridged_multi` | Ridged multifractal | `fastnoise_lite`, `noise_rs` |
| `hybrid_multi` | HybridMulti fractal | `fastnoise_lite`, `noise_rs` |
| `pingpong` | PingPong fractal | `fastnoise_lite`, `noise_rs` |
| `domain_warp` | Domain warping | `fastnoise_lite`, `noise_rs` |
| `combinator` | Generic combinators | `fastnoise_lite`, `noise_rs` |
| `utility` | Utility / deterministic generators | `fastnoise_lite`, `noise_rs` |

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

### Using with Docker

```bash
# Build and run with Docker
docker-compose build
docker-compose up -d

# Access the service
curl http://localhost:8000/v1/algorithms
```

## Testing

To run the tests:

```bash
# Run unit tests
cargo test

# Run integration tests
cd tests && cargo test
```

## Deployment

The service is Docker-ready and can be deployed using:

```bash
# Build the image
docker build -t noise-generation-service .

# Run the container
docker run -p 3000:3000 noise-generation-service
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License.
