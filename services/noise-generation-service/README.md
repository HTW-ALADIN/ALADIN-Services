# Noise Generation Service

## Getting Started
...

## Development
...

## Testing
...

## Noise Generation Service API

### Endpoints

#### 1. Generate Noise
- **Endpoint**: `POST /v1/noise`
- **Description**: Generates noise based on the specified algorithm and backend.
- **Request Body**:
	- `algorithm`: The noise generation algorithm to use (e.g., `perlin`, `simplex`, etc.).
	- `backend`: The backend implementation to use (e.g., `fastnoise_lite`, `noise_rs`).
- **Responses**:
	- `201`: Noise field created.
	- `202`: Noise field generation accepted.

#### 2. Retrieve Noise Field
- **Endpoint**: `GET /v1/noise/{fieldId}`
- **Description**: Retrieves a generated noise field by its ID.
- **Parameters**:
	- `fieldId`: The ID of the noise field to retrieve.
- **Responses**:
	- `200`: Returns the noise field data.

### Algorithm Catalog
- The following algorithms are supported:
	- `perlin`: Perlin noise
	- `simplex`: Simplex noise
	- `opensimplex2`: OpenSimplex2 noise
	- `supersimplex`: SuperSimplex noise
	- `value`: Value noise
	- `cellular`: Cellular noise
	- `fbm`: Fractal Brownian Motion
	- `billow`: Billow noise
	- `ridged_multi`: Ridged multifractal noise
	- `hybrid_multi`: HybridMulti fractal noise
	- `pingpong`: PingPong fractal noise
	- `domain_warp`: Domain warping
	- `combinator`: Generic combinators
	- `utility`: Utility generators

### Testing
- To run the tests, use the following command:
```bash
cargo test
``` 

## Deployment
...
