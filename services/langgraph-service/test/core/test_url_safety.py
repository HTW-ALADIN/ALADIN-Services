"""Unit tests for SSRF-safety checks."""

import pytest

from core.url_safety import UnsafeUrlError, assert_safe_url, is_safe_url, resolve_safe_address


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/api",
        "http://example.com:8080/v1/search",
    ],
)
def test_safe_urls_pass(url):
    assert is_safe_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8003/v1/search",
        "http://127.0.0.1:8000/x",
        "http://10.1.2.3/api",
        "http://192.168.1.10/api",
        "http://172.16.0.5/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/x",
        "ftp://example.com/file",
        "http:///no-host",
    ],
)
def test_unsafe_urls_rejected(url):
    assert is_safe_url(url) is False
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["8.8.8.8", "10.0.0.1"], ["100.64.0.1"], []])
async def test_resolved_nonpublic_addresses_rejected(monkeypatch, addresses):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(0, 0, 0, "", (address, 80)) for address in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(UnsafeUrlError):
        await resolve_safe_address("example.com", 80)


async def test_resolved_public_address_pinned(monkeypatch):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(0, 0, 0, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    assert await resolve_safe_address("example.com", 443) == "8.8.8.8"


@pytest.mark.parametrize("address", ["10.2.3.4", "172.16.0.1", "192.168.1.1", "fd00::1"])
async def test_allowed_internal_addresses(monkeypatch, address):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(0, 0, 0, "", (address, 80))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    assert await resolve_safe_address("sibling", 80, allow_internal=True) == address


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "::1",
        "::ffff:127.0.0.1",
        "169.254.169.254",
        "fe80::1",
        "100.100.100.200",
        "fd00:ec2::254",
    ],
)
async def test_allowlist_never_allows_sensitive_addresses(monkeypatch, address):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(0, 0, 0, "", ("10.1.2.3", 80)), (0, 0, 0, "", (address, 80))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(UnsafeUrlError):
        await resolve_safe_address("sibling", 80, allow_internal=True)


def test_internal_allowlist_config_validation():
    from pydantic import ValidationError

    from config import Settings

    settings = Settings(http_internal_host_allowlist=" Sibling., api.example.com ")
    assert settings.http_internal_host_allowlist == "sibling,api.example.com"
    for host in ("*.example.com", "localhost", "metadata.google.internal.", "127.0.0.1"):
        with pytest.raises(ValidationError):
            Settings(http_internal_host_allowlist=host)
