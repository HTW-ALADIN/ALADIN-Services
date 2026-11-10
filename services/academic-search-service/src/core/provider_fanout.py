"""Shared per-provider dispatch helper.

Both `core/search_service.py` (paper search) and `core/author_search_service.py`
(author search) fan a request out across multiple providers in parallel and
must isolate any single provider's failure -- unknown provider name, missing
credentials, timeout, or an unhandled exception from the backend -- as a
per-provider error rather than letting it fail the whole request. This module
is the single place that dispatch/timeout/error-isolation logic lives, so a
fix to one (e.g. changing the timeout source, or an error message format)
automatically applies to both callers instead of risking silent drift between
two copies of the same logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from config import settings
from core.credentials import resolve_credentials
from core.provider_registry import ProviderSpec, get_provider_spec


async def run_provider[T](
    provider: str,
    credentials: dict[str, dict[str, str]],
    build_coro: Callable[[ProviderSpec, dict[str, str]], Awaitable[T]],
    empty: T,
) -> tuple[T, list[str]]:
    """Resolve `provider`'s spec and credentials, then run
    `build_coro(spec, resolved_credentials)` bounded by
    `settings.provider_timeout_seconds`.

    Returns `(result, errors)`: on any failure (unknown provider, missing
    credentials, timeout, or an unhandled exception from `build_coro`),
    `result` is `empty` and `errors` describes what went wrong -- callers
    never need to catch exceptions themselves.
    """
    try:
        spec = get_provider_spec(provider)
    except KeyError:
        return empty, ["unknown_provider"]

    resolution = resolve_credentials(provider, credentials.get(provider))
    if not resolution.ok:
        return empty, resolution.errors

    try:
        result = await asyncio.wait_for(
            build_coro(spec, resolution.credentials),
            timeout=settings.provider_timeout_seconds,
        )
        return result, []
    except TimeoutError:
        return empty, [f"provider_timeout: exceeded {settings.provider_timeout_seconds}s"]
    except Exception as exc:  # noqa: BLE001 - one provider's failure must not fail the request
        return empty, [f"provider_error: {exc}"]
