# Noise Generation Service

Unified REST API for multiple noise generation libraries and algorithms.

## Features

### Supported Algorithms

| Algorithm | Backend Options | Description | Parameters |
|-----------|----------------|-------------|------------|
| `perlin` | `fastnoise_lite` (default), `noise_rs` | Classic Perlin noise with smooth gradients | `seed` |
| `simplex` | `noise_rs` (only) | Improved noise with lower computational complexity | `seed` |
| `opensimplex2` | `fastnoise_lite` (default), `noise_rs` | Modern variant with better visual quality | `seed` |
| `supersimplex` | `noise_rs` (only) | Higher-dimensional noise variant | `seed` |
| `value` | `fastnoise_lite` (default), `noise_rs` | Grid-based value noise (+cubic interpolation) | `seed` |
| `cellular` | `fastnoise_lite` (default), `noise_rs` (Worley) | Cell-based patterns (Worley/Voronoi) | `seed` |
| `fbm` | `noise_rs` (only) | Fractal Brownian Motion (multi-octave) | `seed`, `octaves`, `frequency`, `lacunarity`, `persistence` |
| `billow` | `noise_rs` (only) | Billow noise (absolute value of Perlin) | `seed`, `octaves`, `frequency`, `lacunarity`, `persistence` |
| `ridged_multi` | `fastnoise_lite` (default), `noise_rs` | Ridge-like fractal patterns | `seed`, `octaves`, `frequency`, `lacunarity` |
| `hybrid_multi` | `noise_rs` (only) | HybridMulti fractal noise | `seed`, `octaves`, `frequency`, `lacunarity` |
| `pingpong` | `fastnoise_lite` (only) | PingPong fractal with wrapping | `seed`, `strength` |
| `domain_warp` | `fastnoise_lite` (only) | Domain warping transformation | `seed`, `amplitude` |
| `combinator` | `noise_rs` (only) | Generic combinators (Add/Multiply/Min/Max/Blend) | `seed`, `op` (`add`/`multiply`/`min`/`max`/`blend`) |
| `utility` | `noise_rs` (only) | Utility generators (Constant/Cylinders) | `kind` (`constant`/`cylinders`), `value` (for constant) |
| `white` | `native` | Pure random white noise | `seed` |

**Total: 14 unique algorithms with 20+ backend/parameter combinations**

### API Endpoints

- `GET /v1/algorithms` — List all available algorithms and backends
- `POST /v1/noise` — Generate noise field and return the full result (including data grid)
- `GET /api-docs/openapi.json` — OpenAPI specification

### Example Requests

#### List Available Algorithms
```bash
curl http://localhost:8000/v1/algorithms
```

#### Generate Perlin Noise
```bash
curl -s -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "perlin",
    "backend": "fastnoise_lite",
    "params": {"seed": 42},
    "sampling": {
      "mode": "2d",
      "dimensions": 2,
      "size": [4, 4]
    }
  }' | jq .
```
Response:
```json
{
  "id": "nsf_abc123...",
  "status": "completed",
  "algorithm": "perlin",
  "data": [[0.23, -0.45, ...], ...],
  "size": [4, 4]
}
```

#### Generate Fractal Brownian Motion
```bash
curl -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "fbm",
    "params": {
      "seed": 123,
      "octaves": 6,
      "frequency": 0.1,
      "lacunarity": 2.0,
      "persistence": 0.5
    },
    "sampling": {
      "mode": "2d", 
      "dimensions": 2,
      "size": [128, 128]
    }
  }'
```

#### Generate Domain-Warped Noise
```bash
curl -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "domain_warp",
    "params": {
      "seed": 999,
      "amplitude": 2.0
    },
    "sampling": {
      "mode": "2d",
      "dimensions": 2,
      "size": [64, 64]
    }
  }'
```

#### Generate Combinator Noise (Add two Perlin sources)
```bash
curl -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "combinator",
    "params": {
      "seed": 555,
      "op": "add"
    },
    "sampling": {
      "mode": "2d",
      "dimensions": 2, 
      "size": [32, 32]
    }
  }'
```

#### Generate Utility Noise (Constant field)
```bash
curl -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "utility",
    "params": {
      "kind": "constant",
      "value": 0.5
    },
    "sampling": {
      "mode": "2d",
      "dimensions": 2,
      "size": [16, 16]
    }
  }'
```

## CLI Usage (Mirroring REST API)

The service includes a **comprehensive CLI** that mirrors **all REST API functionality**.

### List Available Algorithms
```bash
# JSON output (default)
noise-generation-service list

# Table format (human-readable)
noise-generation-service list --format table
```

### Generate Noise Locally (all 14 algorithms)
```bash
# Basic usage (seed defaults to 42 via --param)
noise-generation-service generate --algorithm perlin --width 64 --height 64

# With custom parameters (all algorithms supported)
noise-generation-service generate \
  --algorithm fbm \
  --width 128 --height 128 \
  --param seed=42 \
  --param octaves=6 \
  --param frequency=0.1 \
  --param lacunarity=2.0 \
  --param persistence=0.5 \
  --output noise_field.json

# CSV output
noise-generation-service generate \
  --algorithm white \
  --param seed=999 \
  --width 32 --height 32 \
  --format csv \
  --output noise.csv

# Combinator noise with blend operation
noise-generation-service generate \
  --algorithm combinator \
  --param seed=555 \
  --param op=blend \
  --param blend_factor=0.5 \
  --width 32 --height 32
```

### Start HTTP Server
```bash
# Default (localhost:8000)
noise-generation-service server

# Custom host/port
noise-generation-service server --host 0.0.0.0 --port 9000
```

### Generate OpenAPI Specification
```bash
# Output to stdout
noise-generation-service openapi

# Save to file
noise-generation-service openapi --output api-spec.json

# JSON format (default)
noise-generation-service openapi --format json
```

### CLI Help
```bash
noise-generation-service --help           # All commands
noise-generation-service generate --help  # Command-specific help
```

## Development

### Building
```bash
make build
```

### Testing  
```bash
make test
```

### Running locally
```bash
make start  # Direct execution via cargo run
# OR
cargo run   # Same as make start
# OR  
cargo run -- server --port 8001  # CLI with custom port
```

### Generating OpenAPI spec
```bash
make generate-openapi
# OR
cargo run -- openapi --output spec.json  # Via CLI
```

## Technical Details

- **Language**: Rust (Edition 2021)
- **Web Framework**: Axum 0.7
- **Noise Libraries**: `fastnoise-lite` v1.1.1, `noise` v0.9
- **OpenAPI**: Auto-generated via `utoipa` v4
- **Port**: 8000 (configurable)
- **License**: MIT

## Algorithms Reference

All rows use `POST /v1/noise` with the given `algorithm` tag (and optional `backend` discriminator);
the response includes the full noise field data grid in the `data` field.

> **⚠️ Performance Note:** For large grids (e.g., 1024×1024 or larger), the noise generation will
> take longer and the response payload may become very large (several MB). Consider using smaller
> grid sizes for interactive use, or use the CLI's `generate` command for local generation without
> network overhead. A future enhancement may add HTTP streaming (e.g., `Transfer-Encoding: chunked`)
> for large grid responses.

### Core Noise Algorithms

| `algorithm` tag | Canonical family | Backend options | Underlying function |
|----------------|------------------|-----------------|---------------------|
| `perlin` | Perlin noise | `fastnoise_lite` (default) | `SetNoiseType(Perlin)` + `GetNoise(x, y[, z])` |
| | | `noise_rs` | `Perlin::new(seed).get([x, y])` (or `PerlinSurflet` via `variant` sub-field) |
| `simplex` | Simplex noise (classic) | `noise_rs` (only) | `Simplex::new(seed).get(point)` |
| `opensimplex2` | OpenSimplex2 / OpenSimplex2S | `fastnoise_lite` (default) | `SetNoiseType(OpenSimplex2 \| OpenSimplex2S)` + `GetNoise(x, y[, z])` (variant via `smooth` sub-field) |
| | | `noise_rs` | `OpenSimplex::new(seed).get(point)` |
| `supersimplex` | SuperSimplex | `noise_rs` (only) | `SuperSimplex::new(seed).get(point)` |
| `value` | Value noise (+cubic) | `fastnoise_lite` (default) | `SetNoiseType(Value \| ValueCubic)` + `GetNoise(x, y[, z])` (variant via `interpolation` sub-field) |
| | | `noise_rs` | `Value::new(seed).get(point)` |
| `cellular` | Cellular / Worley / Voronoi | `fastnoise_lite` (default) | `SetNoiseType(Cellular)`, `SetCellularDistanceFunction(...)`, `SetCellularReturnType(...)`, `SetCellularJitter(...)` + `GetNoise(x, y[, z])` |
| | | `noise_rs` | `Worley::new(seed).set_distance_function(...).set_return_type(...).get(point)` |

### Fractal Algorithms

| `algorithm` tag | Canonical family | Backend options | Underlying function |
|----------------|------------------|-----------------|---------------------|
| `fbm` | Fractal Brownian Motion | `fastnoise_lite` (default) | `SetFractalType(FBm)`, `SetFractalOctaves/Lacunarity/Gain(...)` wraps a `source` sub-field (any base algorithm) |
| | | `noise_rs` | `Fbm::<Source>::new(seed).set_octaves/lacunarity/persistence(...).get(point)` |
| `billow` | Billow noise | `noise_rs` (only) | `Billow::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `ridged_multi` | Ridged multifractal | `fastnoise_lite` (default) | `SetFractalType(Ridged)` wraps a `source` sub-field |
| | | `noise_rs` | `RidgedMulti::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `hybrid_multi` | HybridMulti fractal | `noise_rs` (only) | `HybridMulti::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `pingpong` | PingPong fractal | `fastnoise_lite` (only) | `SetFractalType(PingPong)`, `SetFractalPingPongStrength(...)` wraps a `source` sub-field |

### Advanced Algorithms

| `algorithm` tag | Canonical family | Backend options | Underlying function |
|----------------|------------------|-----------------|---------------------|
| `domain_warp` | Domain warping | `fastnoise_lite` (only) | `SetDomainWarpType(...)`, `SetDomainWarpAmp(...)` + `DomainWarp2D/3D(x, y[, z])` |
| `combinator` | Generic combinators | `noise_rs` (only) | `Add`/`Multiply`/`Min`/`Max`/`Blend`/`Turbulence`/`ScalePoint` (selected via `op` sub-field, each wrapping 1–2 `source` sub-fields) |
| `utility` | Utility / deterministic generators | `noise_rs` (only) | `Constant::new(value)` / `Cylinders::new()` (selected via `kind` sub-field) |

### Native White Noise

White noise requires no coherence/interpolation logic and is implemented natively
rather than via an external library. Because it is inherently uncorrelated, its
`params` schema is minimal (`seed` only) and `sampling.mode: "grid"` bypasses
interpolation entirely — each grid cell is sampled independently, so generation
is trivially parallelizable.

| `algorithm` tag | Canonical family | Backend | Underlying function |
|----------------|------------------|---------|---------------------|
| `white` | White noise | `native` (only) | `seeded_prng(seed, x, y, z, w).next_f32() * 2.0 - 1.0` — uncorrelated per-cell/per-point noise, no interpolation |
