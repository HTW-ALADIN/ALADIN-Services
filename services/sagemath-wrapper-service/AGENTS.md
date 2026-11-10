# SageMath Wrapper Agent Guide

## Add an operation

1. Read the relevant `registry/*.yaml` and the existing core module first.
2. Prefer a `kind: template` entry for small, fixed SageMath code. Interpolate
   every input with `|sage_literal` and assign the result to `__result__`.
3. Use `kind: function` only when validation or multi-step logic needs Python.
   Put it in `src/core/`, return JSON-compatible data and raise `ValueError` for
   invalid user input.
4. Use a `function_ref` starting with `src.core.`. Never run a subprocess from
   core code: `src.registry.dispatcher` and `src.sandbox.executor` own process
   isolation, timeouts and resource limits.
5. Keep the registry schema strict enough for the operation, choose the narrowest
   `output_type`, and preserve the public `POST /v1/<operation-id>` contract.

## Security boundaries

- Do not remove JSON Schema validation, Jinja sandboxing, `sage_literal`,
  subprocess execution, CPU/memory/process limits or timeout handling.
- Treat registry templates as trusted repository code, but treat all request
  values as untrusted data.
- Expression-based operations require explicit validation before SageMath parses
  the expression.

## Tests and checks

- Add a focused unit test for Python logic; add a contract test for new API/CLI
  behaviour. Avoid duplicating the same assertion across test layers.
- Run `PYTHONPATH=. python -m pytest tests/unit tests/contract -m 'not docker' -q`.
- Run `python -m ruff check src tests`.
- Run Docker smoke tests only when a Docker daemon is available.

## Keep it small

- Do not add routers, CLI commands or Pydantic models for individual operations;
  the registry generates them.
- Prefer deletion to a new abstraction. Keep helpers only when they are reused
  or protect a security/public-contract boundary.
