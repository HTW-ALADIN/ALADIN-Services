"""Credential Resolver.

Credentials flow through the API/CLI request payload only, never through
service-level environment variables (see config.py). This module validates
per-provider credential presence and produces a per-provider outcome so that
a provider with missing/invalid credentials is skipped -- with an explicit
error recorded -- rather than failing the entire request.

Credentials are never logged and never persisted; callers must treat the
returned dicts as short-lived, request-scoped values.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.provider_registry import get_provider_spec


@dataclass(frozen=True)
class CredentialResolution:
    provider: str
    ok: bool
    credentials: dict[str, str]
    errors: list[str]


def resolve_credentials(
    provider: str,
    supplied: dict[str, str] | None,
) -> CredentialResolution:
    """Validate the credentials supplied for a single provider.

    Args:
        provider: Provider name (must exist in PROVIDER_REGISTRY).
        supplied: The `credentials.<provider>` object from the request, if any.

    Returns:
        A CredentialResolution. `ok=False` means the caller must skip this
        provider (record `errors` in the per-provider response) rather than
        raise -- one provider's missing credentials must never fail the
        whole request.
    """
    spec = get_provider_spec(provider)
    supplied = dict(supplied or {})

    missing_required = [name for name in spec.required_credential_names if not supplied.get(name)]
    if missing_required:
        return CredentialResolution(
            provider=provider,
            ok=False,
            credentials={},
            errors=["missing_credentials"],
        )

    # Only pass through fields this provider actually declares, so an
    # unrelated/typo'd field in the request body is silently ignored rather
    # than forwarded to a backend constructor that doesn't expect it.
    known_fields = {f.name for f in spec.credential_fields}
    filtered = {k: v for k, v in supplied.items() if k in known_fields}
    return CredentialResolution(provider=provider, ok=True, credentials=filtered, errors=[])


def redact(payload: dict) -> dict:
    """Recursively redact credential-shaped fields for safe logging.

    Any key named/containing `credentials`, `api_key`, `token`, or `mailto`
    (case-insensitive) has its value replaced with `"***"`. Used by the
    structured logger before any request payload is logged.
    """
    sensitive_markers = ("credential", "api_key", "apikey", "token", "mailto", "secret")

    def _redact(value: object, key: str | None) -> object:
        if isinstance(value, dict):
            return {k: _redact(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [_redact(v, key) for v in value]
        if key is not None and any(m in key.lower() for m in sensitive_markers):
            return "***"
        return value

    return _redact(payload, None)  # type: ignore[return-value]
