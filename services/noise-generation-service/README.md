# Noise Generation Service



Unified REST API for multiple noise generation libraries and algorithms. The backend library is now automatically selected by default for each requested algorithm.

## Features



### Supported Algorithms



Default libraries are automatically assigned based on the selected algorithm.

| Algorithm | Default Library | Description | Parameters |
| --- | --- | --- | --- |
| `perlin` | `fastnoise_lite`<br> | Classic Perlin noise with smooth gradients

 | `seed`<br> |
| `simplex` | `noise_rs`<br> | Improved noise with lower computational complexity

 | `seed`<br> |
| `opensimplex2` | `fastnoise_lite`<br> | Modern variant with better visual quality

 | `seed`<br> |
| `supersimplex` | `noise_rs`<br> | Higher-dimensional noise variant

 | `seed`<br> |
| `value` | `fastnoise_lite`<br> | Grid-based value noise (+cubic interpolation)

 | `seed`<br> |
| `cellular` | `fastnoise_lite`<br> | Cell-based patterns (Worley/Voronoi)

 | `seed`<br> |
| `fbm` | `noise_rs`<br> | Fractal Brownian Motion (multi-octave)

 | `seed`, `octaves`, `frequency`, `lacunarity`, `persistence`<br> |
| `billow` | `noise_rs`<br> | Billow noise (absolute value of Perlin)

 | `seed`, `octaves`, `frequency`, `lacunarity`, `persistence`<br> |
| `ridged_multi` | `fastnoise_lite`<br> | Ridge-like fractal patterns

 | `seed`, `octaves`, `frequency`, `lacunarity`<br> |
| `hybrid_multi` | `noise_rs`<br> | HybridMulti fractal noise

 | `seed`, `octaves`, `frequency`, `lacunarity`<br> |
| `pingpong` | `fastnoise_lite`<br> | PingPong fractal with wrapping

 | `seed`, `strength`<br> |
| `domain_warp` | `fastnoise_lite`<br> | Domain warping transformation

 | `seed`, `amplitude`<br> |
| `combinator` | `noise_rs`<br> | Generic combinators (Add/Multiply/Min/Max/Blend)

 | `seed`, `op` (`add`/`multiply`/`min`/`max`/`blend`)

 |
| `utility` | `noise_rs`<br> | Utility generators (Constant/Cylinders)

 | `kind` (`constant`/`cylinders`), `value` (for constant)

 |
| `white` | `native`<br> | Pure random white noise

 | `seed`<br> |

**Total: 14 unique algorithms with automatic library selection**

### API Endpoints



* `GET /v1/algorithms` — List all available algorithms and default backends


* `POST /v1/noise` — Generate noise field and return the full result (including data grid)


* `GET /api-docs/openapi.json` — OpenAPI specification



---

### Concrete `params` Object Per Algorithm



`params` is **not** an arbitrary JSON blob. Its shape depends on `algorithm`.
All fields below are optional and use server-side defaults when omitted.

`perlin`, `simplex`, `opensimplex2`, `supersimplex`, `value`, `white`

```json
{ "seed": 42 }

```

`cellular`

```json
{
  "seed": 42,
  "distance_function": "euclidean",   
  "return_type": "cell_value",
  "jitter": 0.45
}

```

Allowed values:

* `distance_function`: `euclidean`, `euclidean_sq`, `manhattan`, `hybrid`

* `return_type`: `cell_value`, `distance`, `distance2`, `distance2_add`, `distance2_sub`, `distance2_mul`, `distance2_div`


`fbm`, `billow`

```json
{
  "seed": 42,
  "octaves": 4,
  "frequency": 0.1,
  "lacunarity": 2.0,
  "persistence": 0.5
}

```

`ridged_multi`, `hybrid_multi`

```json
{
  "seed": 42,
  "octaves": 4,
  "frequency": 0.1,
  "lacunarity": 2.0
}

```

`pingpong`

```json
{
  "seed": 42,
  "strength": 2.0
}

```

`domain_warp`

```json
{
  "seed": 42,
  "amplitude": 1.0
}

```

`combinator`

```json
{
  "seed": 42,
  "op": "add",
  "blend_factor": 0.5
}

```

Allowed values:

* `op`: `add`, `multiply`, `min`, `max`, `blend`


`utility`

```json
{
  "kind": "constant",
  "value": 1.0
}

```

Allowed values:

* `kind`: `constant`, `cylinders`


Defaults used by the service if omitted:

* `seed`: `1`

* `octaves`: `4`

* `frequency`: `0.1`

* `lacunarity`: `2.0`

* `persistence`: `0.5`

* `strength`: `2.0`

* `amplitude`: `1.0`

* `op`: `add`

* `kind`: `constant`

* `value`: `1.0`


---

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

---

## CLI Usage (Mirroring REST API)



The service includes a CLI for local generation, API inspection, and server startup.

### List Available Algorithms



```bash
# JSON output (default)
noise-generation-service list

# Table format (human-readable)
noise-generation-service list --format table

```

### Generate Noise Locally (all 14 algorithms)



```bash
# Basic usage (if omitted, seed defaults to 1 in the service)
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
# Default (0.0.0.0:8000)
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

# YAML output is also supported
noise-generation-service openapi --format yaml

```

### CLI Help



```bash
noise-generation-service --help           # All commands
noise-generation-service generate --help  # Command-specific help

```

---

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

> **Important (utoipa schema registration):** This service uses an explicit `components(schemas(...))` list in `src/lib.rs`. If you add or change nested request models (for example new `params` structs or enums used by `GenerateNoiseRequest`), you must also add those types to that schema list. Otherwise the generated OpenAPI can contain unresolved `$ref` entries.
> 
> 

---

## Technical Details



* **Language**: Rust (Edition 2021)


* **Web Framework**: Axum 0.7


* **Noise Libraries**: `fastnoise-lite` v1.1.1, `noise` v0.9


* **OpenAPI**: Auto-generated via `utoipa` v4


* **Port**: 8000 (configurable)


* **License**: MIT



---

## Algorithms Reference



All rows use `POST /v1/noise` with the given `algorithm` tag; default libraries are selected automatically and the response includes the full noise field data grid in the `data` field.

> **⚠️ Performance Note:** For large grids (e.g., 1024×1024 or larger), the noise generation will take longer and the response payload may become very large (several MB). Consider using smaller grid sizes for interactive use, or use the CLI's `generate` command for local generation without network overhead. A future enhancement may add HTTP streaming (e.g., `Transfer-Encoding: chunked`) for large grid responses.
>
> **📦 Caching Note:** An internal cache for previously generated noise fields is planned as a future update. This would allow re-requesting identical noise fields (same algorithm, parameters, and sampling configuration) without re-computation, improving response times for repeated or shared requests.
> 
> 

### Core Noise Algorithms



| `algorithm` tag | Canonical family | Default Library | Underlying function |
| --- | --- | --- | --- |
| `perlin` | Perlin noise | `fastnoise_lite` | `SetNoiseType(Perlin)` + `GetNoise(x, y[, z])` |
| `simplex` | Simplex noise (classic) | `noise_rs` | `Simplex::new(seed).get(point)` |
| `opensimplex2` | OpenSimplex2 / OpenSimplex2S | `fastnoise_lite` | `SetNoiseType(OpenSimplex2 | OpenSimplex2S)` + `GetNoise(x, y[, z])` (variant via `smooth` sub-field) |
| `supersimplex` | SuperSimplex | `noise_rs` | `SuperSimplex::new(seed).get(point)` |
| `value` | Value noise (+cubic) | `fastnoise_lite` | `SetNoiseType(Value | ValueCubic)` + `GetNoise(x, y[, z])` (variant via `interpolation` sub-field) |
| `cellular` | Cellular / Worley / Voronoi | `fastnoise_lite` | `SetNoiseType(Cellular)`, `SetCellularDistanceFunction(...)`, `SetCellularReturnType(...)`, `SetCellularJitter(...)` + `GetNoise(x, y[, z])` |

### Fractal Algorithms



| `algorithm` tag | Canonical family | Default Library | Underlying function |
| --- | --- | --- | --- |
| `fbm` | Fractal Brownian Motion | `noise_rs` | `Fbm::<Source>::new(seed).set_octaves/lacunarity/persistence(...).get(point)` |
| `billow` | Billow noise | `noise_rs` | `Billow::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `ridged_multi` | Ridged multifractal | `fastnoise_lite` | `SetFractalType(Ridged)` wraps a `source` sub-field |
| `hybrid_multi` | HybridMulti fractal | `noise_rs` | `HybridMulti::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `pingpong` | PingPong fractal | `fastnoise_lite` | `SetFractalType(PingPong)`, `SetFractalPingPongStrength(...)` wraps a `source` sub-field |

### Advanced Algorithms



| `algorithm` tag | Canonical family | Default Library | Underlying function |
| --- | --- | --- | --- |
| `domain_warp` | Domain warping | `fastnoise_lite` | `SetDomainWarpType(...)`, `SetDomainWarpAmp(...)` + `DomainWarp2D/3D(x, y[, z])` |
| `combinator` | Generic combinators | `noise_rs` | `Add`/`Multiply`/`Min`/`Max`/`Blend`/`Turbulence`/`ScalePoint` (selected via `op` sub-field, each wrapping 1–2 `source` sub-fields) |
| `utility` | Utility / deterministic generators | `noise_rs` | `Constant::new(value)` / `Cylinders::new()` (selected via `kind` sub-field) |

### Native White Noise



White noise requires no coherence/interpolation logic and is implemented natively rather than via an external library. Because it is inherently uncorrelated, its `params` schema is minimal (`seed` only) and `sampling.mode: "grid"` bypasses interpolation entirely — each grid cell is sampled independently, so generation is trivially parallelizable.

| `algorithm` tag | Canonical family | Backend | Underlying function |
| --- | --- | --- | --- |
| `white` | White noise | `native` | `seeded_prng(seed, x, y, z, w).next_f32() * 2.0 - 1.0` — uncorrelated per-cell/per-point noise, no interpolation |