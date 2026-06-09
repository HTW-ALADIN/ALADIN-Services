# OpenAI Wrapper Service

HTTP and CLI wrapper around the official OpenAI Responses API.

The service uses the OpenAI Python SDK through the adapter in `src/openai_wrapper_service/client.py`.

- Text generation through the OpenAI Responses API
- A CLI that mirrors the REST behavior
- A generated OpenAPI specification

## Code Layout

```text
src/openai_wrapper_service/api.py      # FastAPI app and routes
src/openai_wrapper_service/client.py   # OpenAI SDK adapter
src/openai_wrapper_service/cli.py      # Command line interface
src/openai_wrapper_service/schemas.py  # Request and response models
scripts/generate_openapi.py            # OpenAPI export utility
```

The service directory uses the repository's kebab-case convention (`openai-wrapper-service`). The Python package uses snake_case (`openai_wrapper_service`) because Python imports cannot contain hyphens.

## Configuration

Set an OpenAI API key before using the API or CLI:

```sh
export OPENAI_API_KEY=...
```

Optional environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_WRAPPER_DEFAULT_RESPONSE_MODEL` | `gpt-5.2` | Default model for `/generate` |
| `OPENAI_WRAPPER_TIMEOUT_SECONDS` | `60` | OpenAI SDK request timeout |

## API

Start the service:

```sh
make start
```

The API listens on port `8002` by default.

OpenAPI docs:

```text
http://localhost:8002/docs
```

Endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `POST` | `/generate` | Generate text through the OpenAI Responses API |

Example generation request:

```json
{
  "input": "Summarize the purpose of ALADIN in one sentence.",
  "instructions": "Answer concisely.",
  "max_output_tokens": 120
}
```

## CLI

The CLI mirrors the API:

```sh
uv run openai-wrapper generate "Write a short explanation of graph rewriting."
uv run openai-wrapper generate "Write a short explanation of graph rewriting." --text-only
```

## Docker

Build:

```sh
make docker-build
```

Run:

```sh
docker run --rm -p 8002:8002 -e OPENAI_API_KEY openai-wrapper-service
```

## Hardware Requirements

Minimal requirements for the wrapper itself:

| Resource | Requirement |
| --- | --- |
| CPU | 1 vCPU |
| Memory | 256 MB RAM |
| Disk | < 200 MB image/runtime overhead, excluding Docker base layers |

Generation latency, availability, and cost are governed by OpenAI API calls rather than local compute. Deployments should enforce request-size and rate limits appropriate for their API budget.

## Development

```sh
make prep
make lint
make test
make generate-openapi
```
