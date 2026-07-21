# LLM Gateway Service

HTTP and CLI wrapper around a **self-hosted [LLM Gateway](https://docs.llmgateway.io/)** instance, built with the
[Vercel AI SDK](https://sdk.vercel.ai/) and [`@llmgateway/ai-sdk-provider`](https://www.npmjs.com/package/@llmgateway/ai-sdk-provider).

This service replaces the former `openai-wrapper-service`. Instead of talking directly to the OpenAI SDK, it routes
text generation and embeddings through LLM Gateway, which can in turn route to OpenAI, Anthropic, Google, and other
providers (including custom OpenAI-compatible endpoints) from one place.

- Non-streaming text generation (chat, system instructions, tool/function-call definitions, vision input)
- Embeddings
- A Vercel AI SDK-shaped request/response format (the format used by the frontend this service backs), behind a
  pluggable adapter so other formats (OpenAI, Anthropic) can be added later — see `src/core/format/`
- A CLI that mirrors the API and is the primary way this service is invoked from workflows (JSON in, JSON out)
- A generated OpenAPI specification

## Code Layout

```text
src/config.ts                          # Environment-driven configuration
src/core/types.ts                      # Format-agnostic request/response model
src/core/gateway-client.ts             # Vercel AI SDK + LLM Gateway client (incl. custom-provider bypass)
src/core/provider-registry.ts          # Best-effort custom provider registration with the gateway
src/core/format/vercel.ts              # Vercel AI SDK wire-format adapter
src/api/                               # Fastify app, routes, and TypeBox schemas
src/cli/                               # Commander-based CLI (generate, register-provider, health)
scripts/generate-openapi.ts            # OpenAPI export utility
```

## Custom providers: registration vs. one-shot calls

LLM Gateway lets you attach any OpenAI-compatible endpoint as a **custom provider**
([docs](https://docs.llmgateway.io/features/custom-providers)), addressed as `{providerName}/{model}`. Normally this
is configured once via the gateway's dashboard.

That doesn't fit a workflow that needs to **deploy this service, point it at a brand-new custom provider, and call
it — all in one automated step** — because:

- LLM Gateway's custom-provider registration is dashboard/session-auth oriented.
- Its only documented bearer-token API ("Master Keys", see [docs](https://docs.llmgateway.io/features/master-keys))
  is **Enterprise-only**, and even then only covers projects, gateway API keys, and IAM rules — **not** custom
  provider/BYOK registration.

So this service supports two paths:

1. **One-shot inline override (recommended for workflows):** pass `customProvider: { baseUrl, apiKey }` on
   `POST /generate` / `POST /embeddings` (or the `generate` CLI command). The request is sent directly to that
   OpenAI-compatible endpoint, **bypassing the gateway entirely** for that call. No prior registration needed —
   this is what makes "deploy + configure + call" possible in a single step. The response is marked
   `viaGatewayBypass: true` since gateway-side cost tracking/analytics don't apply to it.
2. **Best-effort persistent registration:** `POST /providers` / the `register-provider` CLI command attempts to
   register the provider with the gateway via an admin API, if `LLM_GATEWAY_ADMIN_BASE_URL` and
   `LLM_GATEWAY_ADMIN_TOKEN` are configured (e.g. an Enterprise master key or an internal admin endpoint). Without
   that configuration it returns `{"registered": false, "mode": "skipped"}` rather than failing, since the inline
   override above is the reliable path. Use this when you want the gateway itself to track cost/usage for a
   provider that will be reused across many requests.

## Configuration

| Variable                     | Default                    | Description                                                                 |
| ---------------------------- | -------------------------- | --------------------------------------------------------------------------- |
| `LLM_GATEWAY_BASE_URL`       | `http://localhost:4001/v1` | Base URL of the self-hosted LLM Gateway's OpenAI-compatible API             |
| `LLM_GATEWAY_API_KEY`        | unset                      | Bearer token for inference requests against the gateway                     |
| `LLM_GATEWAY_ADMIN_BASE_URL` | unset                      | Base URL of the gateway's admin/management API (best-effort provider setup) |
| `LLM_GATEWAY_ADMIN_TOKEN`    | unset                      | Bearer token for the admin API (e.g. an Enterprise master key)              |
| `LLM_GATEWAY_TIMEOUT_MS`     | `60000`                    | Timeout applied to gateway and custom-provider HTTP calls                   |
| `PORT`                       | `8002`                     | HTTP port used by `make start` and the Docker container                     |
| `HOST`                       | `0.0.0.0`                  | HTTP host to bind                                                           |

The model and provider are supplied per request/CLI call, since available models depend on how the gateway (or a
custom provider) is configured. `LLM_GATEWAY_API_KEY` is only required for requests that route through the gateway;
it is intentionally **not** validated at startup (so `/health` still works without it), but any `/generate` or
`/embeddings` call that isn't using a `customProvider` override will fail fast with a clear error if it's unset,
rather than defaulting to an unauthenticated call.

## Security disclaimer: authentication is NOT provided by this service

**This service has no built-in authentication or authorization on any of its HTTP endpoints** (`/generate`,
`/embeddings`, `/providers`). Anyone who can reach the service over the network can invoke it, including its
`customProvider` bypass — which makes the service issue outbound HTTP requests, with a caller-supplied API key, to
a caller-supplied URL.

**Securing access to this service is a deployment-time obligation delegated to whoever runs/embeds it** — the
consuming system, workflow orchestrator, or platform team deploying this service is responsible for placing it
behind an appropriate auth boundary before it is reachable from anything other than a fully trusted network. This
service does not, and is not intended to, provide that boundary itself. Suitable options include (non-exhaustive):

- Only binding/exposing the service on a private network segment reachable exclusively by the trusted workflow
  system that calls it (e.g. a Kubernetes-internal ClusterIP, a private VPC, or a sidecar-only network namespace).
- Fronting it with an API gateway, reverse proxy, or service mesh that enforces authentication (API keys, mTLS,
  OAuth2/OIDC, network policies) before requests reach this service.
- Wrapping it in an authenticating sidecar/proxy if the deployment platform does not offer the above natively.

Two related mitigations exist in the service itself, but neither is a substitute for an auth boundary:

- `customProvider.baseUrl` is validated to reject loopback, link-local, RFC1918 private ranges, and known cloud
  metadata endpoints (see `src/core/url-safety.ts`) before this service makes any outbound request to it. This is
  a best-effort, static hostname check — it does not resolve DNS, and does not prevent requests to arbitrary
  **public** URLs.
- Missing `LLM_GATEWAY_API_KEY` fails fast with a clear error (see above) rather than silently proceeding.

**Do not expose this service on an untrusted network without first adding an authentication layer in front of it.**

## API

Start the service:

```sh
make start
```

The API listens on port `8002` by default. OpenAPI docs: `http://localhost:8002/docs`.

Endpoints:

| Method | Path          | Description                                                    |
| ------ | ------------- | -------------------------------------------------------------- |
| `GET`  | `/health`     | Liveness probe                                                 |
| `POST` | `/generate`   | Generate text (non-streaming) via LLM Gateway                  |
| `POST` | `/embeddings` | Create embeddings via LLM Gateway                              |
| `POST` | `/providers`  | Best-effort registration of a custom provider with the gateway |

Example generation request:

```json
{
	"provider": "openai",
	"model": "gpt-4o",
	"messages": [{ "role": "user", "content": "Summarize the purpose of ALADIN in one sentence." }],
	"system": "Answer concisely.",
	"maxOutputTokens": 120
}
```

Example one-shot custom provider call (no prior registration required):

```json
{
	"provider": "mycompany",
	"model": "custom-gpt-4",
	"messages": [{ "role": "user", "content": "Hello from my custom provider!" }],
	"customProvider": { "baseUrl": "https://api.mycompany.com", "apiKey": "sk-xxx" }
}
```

## CLI

The CLI mirrors the API and is the primary integration point for workflows. It reads a JSON request from a file or
stdin and writes the full JSON response to stdout or a file:

```sh
npm run cli -- health
echo '{"provider":"openai","model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}' | npm run cli -- generate
npm run cli -- generate request.json -o response.json
npm run cli -- register-provider --name mycompany --base-url https://api.mycompany.com --api-key sk-xxx
```

## Docker

Build:

```sh
make docker-build
```

Run the HTTP API (default):

```sh
docker run --rm -p 8002:8002 \
  -e LLM_GATEWAY_BASE_URL=http://gateway:4001/v1 \
  -e LLM_GATEWAY_API_KEY \
  llm-gateway-service
```

Run the CLI instead:

```sh
docker run --rm -i \
  -e LLM_GATEWAY_BASE_URL=http://gateway:4001/v1 \
  -e LLM_GATEWAY_API_KEY \
  llm-gateway-service \
  node_modules/.bin/tsx src/cli/index.ts generate - < request.json
```

## Development

```sh
make prep
make lint
make test
make generate-openapi
```

Tests mock the LLM Gateway/AI SDK boundary (a local HTTP server standing in for an OpenAI-compatible endpoint, plus
dependency-injected fakes for the API/CLI layers) — no live network calls are made in CI.
