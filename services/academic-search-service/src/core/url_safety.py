"""SSRF-safety checks and DNS resolution for provider-returned URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import socket

import httpx

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


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and (
        ip.scope_id is not None
        or ip.ipv4_mapped is not None
        or ip.sixtofour is not None
        or ip.teredo is not None
    ):
        return False
    return (
        ip.is_global
        and not ip.is_private
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
    )


def _parse_safe_url(url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, UnicodeError) as exc:
        raise UnsafeUrlError("Invalid URL") from exc

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Unsafe URL scheme: {parsed.scheme!r}")

    host = parsed.raw_host.decode("ascii")
    if not host or not host.rstrip("."):
        raise UnsafeUrlError("URL has no host")
    if parsed.userinfo:
        raise UnsafeUrlError("URL credentials are not allowed")
    if "%" in host or "\\" in host:
        raise UnsafeUrlError("URL host contains an unsupported escape or scope")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise UnsafeUrlError("URL port is out of range")

    normalized_host = host.rstrip(".")
    if normalized_host in _BLOCKED_HOSTS:
        raise UnsafeUrlError(f"URL host is a known cloud metadata endpoint: {host}")
    if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
        raise UnsafeUrlError(f"URL host is loopback: {host}")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _is_public_ip(address):
            raise UnsafeUrlError(f"URL host is a non-public IP literal: {host}")
    return parsed


def assert_safe_url(url: str) -> None:
    _parse_safe_url(url)


async def resolve_safe_url(url: str, timeout: float) -> tuple[httpx.URL, tuple[str, ...]]:
    parsed = _parse_safe_url(url)
    host = parsed.raw_host.decode("ascii")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    try:
        addresses = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM),
            timeout=timeout,
        )
    except (OSError, TimeoutError, UnicodeError) as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc

    resolved = []
    for family, _, _, _, sockaddr in addresses:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise UnsafeUrlError("URL host resolved to an unsupported address family")
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except (IndexError, ValueError) as exc:
            raise UnsafeUrlError("URL host resolved to an invalid IP address") from exc
        if address.version != (4 if family == socket.AF_INET else 6):
            raise UnsafeUrlError("URL host resolved to an invalid IP address")
        if family == socket.AF_INET6 and sockaddr[3]:
            raise UnsafeUrlError("URL host resolved to a scoped IPv6 address")
        if not _is_public_ip(address):
            raise UnsafeUrlError("URL host resolves to a non-public IP address")
        resolved.append(str(address))

    if not resolved:
        raise UnsafeUrlError("URL host did not resolve to an IP address")
    return parsed, tuple(dict.fromkeys(resolved))


def is_safe_url(url: str) -> bool:
    try:
        assert_safe_url(url)
    except UnsafeUrlError:
        return False
    return True
