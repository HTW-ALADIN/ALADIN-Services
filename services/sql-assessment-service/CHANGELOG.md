# Changelog

All notable changes to the sql-assessment-service are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **BREAKING:** the `OPENAI_API_KEY`-based LLM configuration has been removed.
  The service no longer reads `OPENAI_API_KEY` (or any other environment
  variable) to enable, configure, or authenticate LLM work. LLM availability
  for a request is now determined solely by the presence of a usable
  `llmGateway` block on that request.

  **Caller migration:** send an `llmGateway` block on every request that
  should use LLM-backed descriptions:

  ```json
  {
    "llmGateway": {
      "endpoint": "http://llm-gateway:8080",
      "apiKey": "<gateway key>",
      "provider": "openai",
      "model": "gpt-4o-mini"
    }
  }
  ```

  `endpoint` and `apiKey` are required; `provider` (default `openai`) and
  `model` (default `gpt-4o-mini`) are optional overrides. The `apiKey` is sent
  as an `Authorization: Bearer` header and is never logged.

  When a request carries no usable `llmGateway` block, every LLM-dependent
  description variant falls back to the template engine and all response
  shapes remain unchanged, so callers that send no block keep working with
  template-only behavior instead of failing.

### Added

- `llmGateway` request block on `GET /api/generation/generate`,
  `POST /api/description/llm/*`, `POST /api/description/hybrid`, and
  `POST /api/grading/grade` for per-request gateway routing and credentials.
- Generic LLM gateway client speaking the llm-gateway-service
  `POST /generate` wire format (Vercel AI SDK `UIMessage` format — the
  gateway's default), replacing the hardcoded OpenAI/LangChain integration.
  Provider-specific client libraries were removed.
- `llmGateway.customProvider` override (`baseUrl` + `apiKey`) that lets a
  request bypass the gateway's provider registration and call an arbitrary
  OpenAI-compatible endpoint directly.
- Case-sensitive identifier support: all SQL the service constructs itself
  (predicate sampling probes and the final generated query) now quotes
  identifiers per PostgreSQL double-quote rules, so databases with quoted
  uppercase identifiers (e.g. the KE2 teaching database) generate and execute
  tasks correctly.
