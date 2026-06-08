# Noise Generation Service

HTTP and CLI wrapper for deterministic procedural noise fields used to create practice data for geo-informatics and geostatistical interpolation exercises.

The service exposes scalar noise grids and contour-style SVG plots. It uses `pyfastnoiselite`, a Python wrapper around FastNoiseLite, through the adapter in `src/noise_generation_service/generator.py`.

## API

Start the service:

```sh
make start
```

The API listens on port `8001` by default.

OpenAPI docs:

```text
http://localhost:8001/docs
```

Endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `POST` | `/noise/grid` | Return a deterministic 2D scalar grid as JSON |
| `POST` | `/noise/contour.svg` | Return a contour-style SVG plot |

Example request:

```json
{
  "width": 80,
  "height": 80,
  "seed": 42,
  "scale": 24.0,
  "octaves": 5,
  "persistence": 0.5,
  "lacunarity": 2.0,
  "levels": 10,
  "samplePoints": 8
}
```

## CLI

The CLI mirrors the API outputs:

```sh
uv run noise-generation grid --width 80 --height 80 --seed 42 --output grid.json
uv run noise-generation contour --width 80 --height 80 --seed 42 --output contour.svg
```

Without `--output`, the generated JSON or SVG is written to stdout.

## Docker

Build:

```sh
make docker-build
```

Run:

```sh
docker run --rm -p 8001:8001 noise-generation-service
```

## Hardware Requirements

Minimal requirements for the default API limits:

| Resource | Requirement |
| --- | --- |
| CPU | 1 vCPU |
| Memory | 256 MB RAM |
| Disk | < 200 MB image/runtime overhead, excluding Docker base layers |

The default request limit is `512 x 512` grid cells. Larger grids should be guarded by deployment-level request limits or implemented as asynchronous jobs.

## Development

```sh
make prep
make lint
make test
make generate-openapi
```
