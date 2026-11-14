"""SSRF-safety checks for caller-supplied HTTP node URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

# Known cloud metadata endpoints that must never be reachable from this service.
_BLOCKED_HOSTS = {
    "169.254.169.254",  # AWS/GCP/Azure/OpenStack metadata
    "metadata.google.internal",
    "metadata.azure.com",
    "100.100.100.200",  # Alibaba Cloud metadata
    "fd00:ec2::254",
}

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeUrlError(ValueError):
    """Raised when a URL fails the SSRF-safety check."""


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global or ip.is_multicast


def normalize_internal_hostname(host: str) -> str:
    try:
        name = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError(f"Invalid internal hostname: {host!r}") from exc
    if (
        not name
        or len(name) > 253
        or name in _BLOCKED_HOSTS
        or name == "localhost"
        or name.endswith(".localhost")
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in name.split(".")
        )
    ):
        raise ValueError(f"Invalid internal hostname: {host!r}")
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return name
    raise ValueError(f"Internal allowlist requires hostnames, not IP addresses: {host!r}")


def _allowed_address(address: str, allow_internal: bool) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if (
        str(ip) in _BLOCKED_HOSTS
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or (isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local)
    ):
        return False
    if ip.is_global:
        return True
    internal_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("fc00::/7"),
    )
    return allow_internal and any(ip in network for network in internal_networks)


async def resolve_safe_address(host: str, port: int, *, allow_internal: bool = False) -> str:
    try:
        records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeUrlError(f"URL host could not be resolved: {host}") from exc
    addresses = [record[4][0] for record in records]
    if not addresses or any(not _allowed_address(address, allow_internal) for address in addresses):
        raise UnsafeUrlError(f"URL host resolves to a non-public address: {host}")
    return addresses[0]


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

    host = (parsed.hostname or "").lower().rstrip(".")
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
