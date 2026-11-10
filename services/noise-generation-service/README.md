# Noise Generation Service



Unified REST API for multiple noise generation libraries and algorithms.

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

**Total: 15 unique algorithms with automatic library selection**

### API Endpoints



* `GET /v1/algorithms` — List all available algorithms with their default parameters


* `POST /v1/noise` — Generate noise field and return the full result (including data grid)

  The `sampling.size` field determines the dimensionality of the result:

  - `[width]` — 1D array
  - `[width, height]` — 2D grid (nested arrays)
  - `[width, height, depth]` — 3D volume (triple-nested arrays)
  - `[width, height, depth, time]` — 4D hypervolume (4×-nested arrays)

  **4D support** is available for noise-rs algorithms (simplex, fbm, billow,
  ridged_multi, hybrid_multi, combinator, utility) and white noise.
  FNL-based algorithms (perlin, opensimplex2, value, cellular, pingpong,
  domain_warp) and supersimplex are limited to 2D/3D.
  White noise additionally supports 1D.
  Requesting an unsupported dimension returns a 400 error with a descriptive message.

  **Response includes `params_used`**: Every successful response contains a
  `params_used` field that echoes all resolved parameters (including applied
  defaults and the effective seed). This makes every generated noise field
  fully reproducible — even when the caller omitted optional parameters or
  left the seed unset (in which case the randomly generated seed is included
  in the response).


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
  "lacunarity": 2.0,
  "persistence": 0.5
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

* `seed`: randomly generated per request (based on current time) if omitted — not deterministic

* `octaves`: `4`

* `frequency`: `0.1`

* `lacunarity`: `2.0`

* `persistence`: `0.5` (Fbm, Billow), `0.5` (RidgedMulti), `0.25` (HybridMulti)

* `strength`: `2.0`

* `amplitude`: `1.0`

* `op`: `add`

* `kind`: `constant`

* `value`: `1.0`

> **Why are parameters still optional?** All fields remain optional so that the
> service stays easily callable by AI agents or quick scripts with minimal context.
> However, **reproducibility is now guaranteed** via two mechanisms:
> 1. **`POST /v1/noise` response** includes a `params_used` field that echoes all
>    resolved parameter values (including the effective seed).
> 2. **`GET /v1/algorithms`** lists every algorithm together with its server-side
>    default values, enabling clients to inspect defaults without reading docs.
>
> This way you get both convenience (optional fields) and full traceability
> (resolved values in the response + discoverable defaults via the API).


### GET /v1/algorithms Response

The endpoint now returns an array of objects, each containing the algorithm
name and its default parameter values:

```json
[
  {
    "name": "perlin",
    "defaults": { "seed": null }
  },
  {
    "name": "cellular",
    "defaults": {
      "seed": null,
      "distance_function": "euclidean",
      "return_type": "cell_value",
      "jitter": 0.45
    }
  },
  {
    "name": "fbm",
    "defaults": {
      "seed": null,
      "octaves": 4,
      "frequency": 0.1,
      "lacunarity": 2.0,
      "persistence": 0.5
    }
  },
  ...
]
```

> The `seed` default shows as `null` because seeds are randomly generated per
> request when omitted. The actual effective seed for a specific response is
> always included in `params_used` in the `POST /v1/noise` response.

**CLI output (`noise-generation-service list`)**:

- **JSON format** (`--format json`, default): Returns the same structured array
  as the REST endpoint.
- **CSV format** (`--format csv`): Lists algorithm name and defaults
  (as a compact JSON string in a second column).


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
  "size": [4, 4],
  "params_used": {
    "seed": 42
  }
}

```

#### Generate Perlin Noise Without Seed (auto-generated seed in response)

```bash
curl -s -X POST http://localhost:8000/v1/noise \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "perlin",
    "params": {},
    "sampling": {
      "size": [4, 4]
    }
  }' | jq .

```

Response (seed is auto-generated but echoed back):

```json
{
  "id": "nsf_def456...",
  "status": "completed",
  "algorithm": "perlin",
  "data": [[-0.12, 0.34, ...], ...],
  "size": [4, 4],
  "params_used": {
    "seed": 3714829405
  }
}
```

> The `params_used` field contains the effective seed even when none was provided.
> Save this value to reproduce the identical noise field later.

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
      "size": [16, 16]
    }
  }'

```

---

## CLI Usage (Mirroring REST API)



The service includes a CLI for local generation, API inspection, and server startup.

### List Available Algorithms



```bash
# JSON output (default) — returns structured array with name + defaults
noise-generation-service list

# CSV output — "algorithm","defaults" columns
noise-generation-service list --format csv

```

### Generate Noise Locally (all 15 algorithms)

Parameters are passed as a single JSON object via `--params`, and grid size via
`--sampling-size` (or the deprecated alias `--size`; 1–4 comma-separated
values: `width` for 1D, `width,height` for 2D, `width,height,depth` for 3D,
`width,height,depth,time` for 4D; defaults to `64,64` if omitted).

> **CLI-API mapping**: `--sampling-size` → `sampling.size`,
> `--output-format` → `output.format`,
> `--output-normalize` → `output.normalize`.
> `--output-file` is CLI-only (not part of the API schema).
> Deprecated aliases (`--size`, `--format`, `--normalize`) still work for
> backward compatibility.

```bash
# Basic usage (if --params is omitted, seed is chosen at random by the service)
noise-generation-service generate --algorithm perlin --sampling-size 64,64

# With custom parameters (all algorithms supported)
noise-generation-service generate \
  --algorithm fbm \
  --sampling-size 128,128 \
  --params '{"seed": 42, "octaves": 6, "frequency": 0.1, "lacunarity": 2.0, "persistence": 0.5}' \
  --output-file noise_field.json

# CSV output
noise-generation-service generate \
  --algorithm white \
  --params '{"seed": 999}' \
  --sampling-size 32,32 \
  --output-format csv \
  --output-file noise.csv

# Combinator noise with blend operation
noise-generation-service generate \
  --algorithm combinator \
  --params '{"seed": 555, "op": "blend", "blend_factor": 0.5}' \
  --sampling-size 32,32

# Normalize output values to [0,1]
noise-generation-service generate --algorithm perlin --output-normalize

# CSV output is limited to 1D/2D data; 3D/4D requests will error:
noise-generation-service generate --algorithm white --sampling-size 4,4,4 --output-format csv
# → Error: CSV output only supports 1D/2D noise fields; use --output-format json for 3D data

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
| `opensimplex2` | OpenSimplex2 / OpenSimplex2S | `fastnoise_lite` | `SetNoiseType(OpenSimplex2 | OpenSimplex2S)` + `GetNoise(x, y[, z])` |
| `supersimplex` | SuperSimplex | `noise_rs` | `SuperSimplex::new(seed).get(point)` |
| `value` | Value noise (+cubic) | `fastnoise_lite` | `SetNoiseType(Value | ValueCubic)` + `GetNoise(x, y[, z])` |
| `cellular` | Cellular / Worley / Voronoi | `fastnoise_lite` | `SetNoiseType(Cellular)`, `SetCellularDistanceFunction(...)`, `SetCellularReturnType(...)`, `SetCellularJitter(...)` + `GetNoise(x, y[, z])` |

### Fractal Algorithms



| `algorithm` tag | Canonical family | Default Library | Underlying function |
| --- | --- | --- | --- |
| `fbm` | Fractal Brownian Motion | `noise_rs` | `Fbm::<Source>::new(seed).set_octaves/lacunarity/persistence(...).get(point)` |
| `billow` | Billow noise | `noise_rs` | `Billow::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `ridged_multi` | Ridged multifractal | `fastnoise_lite` | `SetFractalType(Ridged)`, `SetFrequency(...)`, `SetFractalOctaves(...)`, `SetFractalLacunarity(...)`, `SetFractalGain(...)` |
| `hybrid_multi` | HybridMulti fractal | `noise_rs` | `HybridMulti::<Source>::new(seed).set_octaves/...(...).get(point)` |
| `pingpong` | PingPong fractal | `fastnoise_lite` | `SetFractalType(PingPong)`, `SetFractalPingPongStrength(...)` |

### Advanced Algorithms



| `algorithm` tag | Canonical family | Default Library | Underlying function |
| --- | --- | --- | --- |
| `domain_warp` | Domain warping | `fastnoise_lite` | `SetDomainWarpType(...)`, `SetDomainWarpAmp(...)` + `DomainWarp2D/3D(x, y[, z])` |
| `combinator` | Generic combinators | `noise_rs` | `Add`/`Multiply`/`Min`/`Max`/`Blend` (selected via `op` sub-field), each wrapping two Perlin sources with seeds `seed` and `seed+1` |
| `utility` | Utility / deterministic generators | `noise_rs` | `Constant::new(value)` / `Cylinders::new()` (selected via `kind` sub-field) |

### Native White Noise



White noise requires no coherence/interpolation logic and is implemented natively rather than via an external library. Because it is inherently uncorrelated, its `params` schema is minimal (`seed` only) — each grid cell is sampled independently, so generation is trivially parallelizable.

| `algorithm` tag | Canonical family | Underlying function |
| --- | --- | --- |
| `white` | White noise | `seeded_prng(seed, x, y, z, w).next_f32() * 2.0 - 1.0` — uncorrelated per-cell/per-point noise, no interpolation |