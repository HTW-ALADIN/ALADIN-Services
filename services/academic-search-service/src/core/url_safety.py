"""SSRF-safety checks for provider-returned URLs.

Ports the category of check `llm-gateway-service/src/core/url-safety.ts` applies
to caller-supplied URLs, to the different risk shape this service has: it fetches
`pdf_url`/full-text URLs that come back FROM third-party provider responses
(not directly from the caller), which are not fully trusted input either.

Best-effort only: this performs a static hostname/IP-literal check and does not
resolve DNS, so it does not catch a hostname that only *resolves* to a private
address. It does not replace network-level egress controls.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

# Known cloud metadata endpoints that must never be reachable from this service.
_BLOCKED_HOSTS = {
    "169.254.169.254",  # AWS/GCP/Azure/OpenStack metadata
    "metadata.google.internal",
    "metadata.azure.com",
    "100.100.100.200",  # Alibaba Cloud metadata
}

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeUrlError(ValueError):
    """Raised when a URL fails the SSRF-safety check."""


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Raise UnsafeUrlError if `url` must not be fetched server-side.

    Rejects:
    - non-http(s) schemes
    - loopback / link-local / RFC1918 private ranges (IP literals)
    - known cloud metadata hostnames/IPs
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Unsafe URL scheme: {parsed.scheme!r}")

    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("URL has no host")

    if host in _BLOCKED_HOSTS:
        raise UnsafeUrlError(f"URL host is a known cloud metadata endpoint: {host}")

    if host in ("localhost",) or host.endswith(".localhost"):
        raise UnsafeUrlError(f"URL host is loopback: {host}")

    if _is_private_ip(host):
        raise UnsafeUrlError(f"URL host resolves to a private/reserved IP literal: {host}")


def is_safe_url(url: str) -> bool:
    try:
        assert_safe_url(url)
    except UnsafeUrlError:
        return False
    return True
