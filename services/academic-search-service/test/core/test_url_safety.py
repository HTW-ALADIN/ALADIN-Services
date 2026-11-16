import asyncio
import socket

import pytest

from core.url_safety import UnsafeUrlError, assert_safe_url, is_safe_url, resolve_safe_url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/",
        "http://metadata.google.internal./",
        "http://127.0.0.1/",
        "http://localhost/",
        "http://localhost./",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://100.64.0.1/",
        "http://224.0.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[2002:0808:0808::]/",
        "http://user:password@example.org/",
        "http://%31%32%37.0.0.1/",
        "http://[::1",
        "https://example.org:65536/paper.pdf",
        "ftp://example.org/file.pdf",
    ],
)
def test_unsafe_urls_rejected(url):
    assert not is_safe_url(url)
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://arxiv.org/pdf/2401.00001.pdf",
        "http://example.com/paper.pdf",
    ],
)
def test_safe_urls_accepted(url):
    assert is_safe_url(url)
    assert_safe_url(url)


def _address_info(address, port):
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.5"],
        ["169.254.169.254"],
        ["100.64.0.1"],
        ["224.0.0.1"],
        ["::1"],
        ["fd00::1"],
        ["fe80::1"],
        ["::ffff:127.0.0.1"],
        ["ff02::1"],
        ["93.184.216.34", "10.0.0.1"],
        ["127.0.0.1", "2606:4700:4700::1111"],
    ],
)
async def test_resolve_rejects_non_public_dns_answers(monkeypatch, addresses):
    async def getaddrinfo(host, port, **kwargs):
        assert host == "papers.example.org"
        return [_address_info(address, port) for address in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    with pytest.raises(UnsafeUrlError, match="non-public"):
        await resolve_safe_url("https://papers.example.org/paper.pdf", 1)


@pytest.mark.parametrize("address", ["93.184.216.34", "2606:4700:4700::1111"])
async def test_resolve_accepts_and_returns_public_address(monkeypatch, address):
    async def getaddrinfo(host, port, **kwargs):
        assert host == "papers.example.org"
        assert port == 8443
        return [_address_info(address, port)]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    url, resolved = await resolve_safe_url("https://papers.example.org:8443/paper.pdf", 1)
    assert url.host == "papers.example.org"
    assert resolved == (address,)


async def test_resolve_returns_all_unique_public_addresses(monkeypatch):
    async def getaddrinfo(host, port, **kwargs):
        return [
            _address_info("93.184.216.34", port),
            _address_info("2606:4700:4700::1111", port),
            _address_info("93.184.216.34", port),
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    _, resolved = await resolve_safe_url("https://papers.example.org/paper.pdf", 1)
    assert resolved == ("93.184.216.34", "2606:4700:4700::1111")


@pytest.mark.parametrize("failure", ["error", "unicode", "empty", "timeout"])
async def test_resolve_fails_closed_on_dns_failures(monkeypatch, failure):
    async def getaddrinfo(host, port, **kwargs):
        if failure == "error":
            raise socket.gaierror(socket.EAI_NONAME, "no such host")
        if failure == "unicode":
            raise UnicodeError("invalid DNS label")
        if failure == "timeout":
            await asyncio.sleep(1)
        return []

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    with pytest.raises(UnsafeUrlError):
        await resolve_safe_url("https://papers.example.org/paper.pdf", 0.01)


async def test_resolve_rejects_scoped_ipv6_dns_answer(monkeypatch):
    async def getaddrinfo(host, port, **kwargs):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", port, 0, 1))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    with pytest.raises(UnsafeUrlError, match="scoped"):
        await resolve_safe_url("https://papers.example.org/paper.pdf", 1)
