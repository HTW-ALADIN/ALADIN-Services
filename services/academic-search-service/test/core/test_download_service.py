import asyncio
import socket
import ssl
from pathlib import Path
from unittest.mock import AsyncMock

import httpcore
import pytest
from httpcore._backends.auto import AutoBackend

from adapters import academic_mcp_adapter, scimesh_adapter
from config import settings
from core import download_service, fulltext_service
from core.download_service import download_one
from core.fulltext_service import FulltextUnavailableError, read_fulltext
from core.paper import Paper


async def test_download_one_unknown_provider():
    result = await download_one("not-a-provider", "x", {})
    assert result.status == "error"
    assert result.error == "unknown_provider"


async def test_download_one_missing_credentials():
    result = await download_one("scopus", "x", {})
    assert result.status == "error"
    assert result.error == "missing_credentials"


async def test_download_one_scimesh_not_found(monkeypatch):
    async def _fake_get(provider, credentials, paper_id):
        return None

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)

    result = await download_one("arxiv", "2401.00001", {})
    assert result.status == "not_found"


async def test_download_one_scimesh_no_pdf_url(monkeypatch):
    async def _fake_get(provider, credentials, paper_id):
        return Paper(
            id="sha256:x", provider=provider, backend="scimesh", title="X", open_access=False
        )

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)

    result = await download_one("arxiv", "2401.00001", {})
    assert result.status == "paywalled"


class _FakeNetworkStream:
    def __init__(self, response):
        self.response = response
        self.request = b""
        self.server_hostname = None
        self.check_hostname = None
        self.verify_mode = None

    async def start_tls(self, ssl_context, server_hostname, timeout=None):
        self.server_hostname = server_hostname
        self.check_hostname = ssl_context.check_hostname
        self.verify_mode = ssl_context.verify_mode
        return self

    async def write(self, data, timeout=None):
        self.request += data

    async def read(self, max_bytes, timeout=None):
        response, self.response = self.response, b""
        return response

    async def aclose(self):
        pass

    def get_extra_info(self, info):
        return None


def _mock_scimesh_pdf(monkeypatch, tmp_path, url):
    async def get(provider, credentials, paper_id):
        return Paper(id="sha256:x", provider=provider, backend="scimesh", title="X", pdf_url=url)

    monkeypatch.setattr(scimesh_adapter, "get", get)
    monkeypatch.setattr(download_service, "_dest_dir", lambda: str(tmp_path))


def _dns_answer(address, port):
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))


@pytest.mark.parametrize(
    ("host", "address"),
    [
        ("papers.example.org", "93.184.216.34"),
        ("papers.example.org", "2606:4700:4700::1111"),
        ("8.8.8.8", "8.8.8.8"),
        ("[2606:4700:4700::1111]", "2606:4700:4700::1111"),
    ],
)
async def test_scimesh_pins_dns_and_preserves_host_and_tls(monkeypatch, tmp_path, host, address):
    _mock_scimesh_pdf(monkeypatch, tmp_path, f"https://{host}:8443/file.pdf?q=a%2Fb")
    lookups = []
    connections = []
    stream = _FakeNetworkStream(
        b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
    )

    async def getaddrinfo(host, port, **kwargs):
        lookups.append((host, port))
        answer = address if len(lookups) == 1 else "127.0.0.1"
        return [_dns_answer(answer, port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return stream

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert Path(result.path).read_bytes() == b"%PDF-1.7"
    assert lookups == [(host.strip("[]"), 8443)]
    assert connections == [(address, 8443)]
    assert stream.server_hostname == host.strip("[]")
    assert stream.check_hostname is True
    assert stream.verify_mode == ssl.CERT_REQUIRED
    assert b"GET /file.pdf?q=a%2Fb HTTP/1.1\r\n" in stream.request
    assert f"\r\nhost: {host}:8443\r\n".encode() in stream.request.lower()


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("https://private.example.org/paper.pdf", ["127.0.0.1"]),
        ("https://private.example.org/paper.pdf", ["fd00::1"]),
        ("https://mixed.example.org/paper.pdf", ["93.184.216.34", "169.254.169.254"]),
        ("http://2130706433/paper.pdf", ["127.0.0.1"]),
    ],
)
async def test_scimesh_rejects_unsafe_dns_without_connecting(monkeypatch, tmp_path, url, addresses):
    _mock_scimesh_pdf(monkeypatch, tmp_path, url)
    connect_tcp = AsyncMock()

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer(address, port) for address in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert "non-public" in result.error
    connect_tcp.assert_not_awaited()
    assert not list(tmp_path.iterdir())


def _redirect_response(status, location, extra_headers=""):
    return (
        f"HTTP/1.1 {status} Redirect\r\nLocation: {location}\r\n"
        f"{extra_headers}Content-Length: 0\r\n\r\n"
    ).encode()


async def test_arxiv_relative_redirect_revalidates_dns_and_keeps_cookies(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://arxiv.org/pdf/2401.00001")
    lookups = []
    connections = []
    streams = [
        _FakeNetworkStream(
            _redirect_response(
                302,
                "/pdf/2401.00001.pdf?download=1",
                "Set-Cookie: session=arxiv; Path=/; Secure\r\n",
            )
        ),
        _FakeNetworkStream(
            b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
        ),
    ]

    async def getaddrinfo(host, port, **kwargs):
        lookups.append((host, port))
        addresses = ["93.184.216.34", "8.8.8.8"]
        return [_dns_answer(addresses[len(lookups) - 1], port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return streams[len(connections) - 1]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert Path(result.path).read_bytes() == b"%PDF-1.7"
    assert lookups == [("arxiv.org", 443), ("arxiv.org", 443)]
    assert connections == [("93.184.216.34", 443), ("8.8.8.8", 443)]
    assert all(stream.server_hostname == "arxiv.org" for stream in streams)
    assert b"GET /pdf/2401.00001.pdf?download=1 HTTP/1.1\r\n" in streams[1].request
    assert b"\r\nhost: arxiv.org\r\n" in streams[1].request.lower()
    assert b"\r\ncookie: session=arxiv\r\n" in streams[1].request.lower()


async def test_arxiv_http_to_https_redirect_revalidates_port(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "http://arxiv.org/pdf/2401.00001")
    lookups = []
    connections = []
    streams = [
        _FakeNetworkStream(_redirect_response(301, "https://arxiv.org/pdf/2401.00001.pdf")),
        _FakeNetworkStream(
            b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
        ),
    ]

    async def getaddrinfo(host, port, **kwargs):
        lookups.append((host, port))
        return [_dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return streams[len(connections) - 1]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert lookups == [("arxiv.org", 80), ("arxiv.org", 443)]
    assert connections == [("93.184.216.34", 80), ("93.184.216.34", 443)]
    assert streams[0].server_hostname is None
    assert streams[1].server_hostname == "arxiv.org"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize(
    ("location", "port", "authority"),
    [
        ("https://pdfs.example.org/remote.pdf?download=1", 443, "pdfs.example.org"),
        ("//pdfs.example.org/remote.pdf?download=1", 443, "pdfs.example.org"),
        ("https://pdfs.example.org:8443/remote.pdf?download=1", 8443, "pdfs.example.org:8443"),
    ],
)
async def test_redirect_to_public_host_repins_and_reverifies_tls(
    monkeypatch, tmp_path, status, location, port, authority
):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    lookups = []
    connections = []
    streams = [
        _FakeNetworkStream(
            _redirect_response(
                status,
                location,
                "Set-Cookie: session=private; Path=/; Secure\r\n",
            )
        ),
        _FakeNetworkStream(
            b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
        ),
    ]

    async def getaddrinfo(host, port, **kwargs):
        lookups.append((host, port))
        return [_dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return streams[len(connections) - 1]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert Path(result.path).read_bytes() == b"%PDF-1.7"
    assert lookups == [("papers.example.org", 443), ("pdfs.example.org", port)]
    assert connections == [("93.184.216.34", 443), ("93.184.216.34", port)]
    assert [stream.server_hostname for stream in streams] == [
        "papers.example.org",
        "pdfs.example.org",
    ]
    assert all(
        stream.check_hostname and stream.verify_mode == ssl.CERT_REQUIRED for stream in streams
    )
    assert b"GET /remote.pdf?download=1 HTTP/1.1\r\n" in streams[1].request
    assert f"\r\nhost: {authority}\r\n".encode() in streams[1].request.lower()
    assert b"\r\ncookie:" not in streams[1].request.lower()


@pytest.mark.parametrize(
    ("location", "addresses"),
    [
        ("http://127.0.0.1/private", None),
        ("http://169.254.169.254/latest/meta-data/", None),
        ("http://metadata.google.internal./", None),
        ("http://internal.example.org/private", ["127.0.0.1"]),
        ("http://internal.example.org/private", ["fd00::1"]),
        ("http://internal.example.org/private", ["93.184.216.34", "10.0.0.1"]),
        ("http://2130706433/private", ["127.0.0.1"]),
        ("https://user:password@other.example.org/private", None),
        ("http://[::1", None),
        ("ftp://other.example.org/private", None),
    ],
)
async def test_redirect_to_unsafe_url_never_connects(monkeypatch, tmp_path, location, addresses):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        if host == "papers.example.org":
            return [_dns_answer("93.184.216.34", port)]
        assert addresses is not None
        return [_dns_answer(address, port) for address in addresses]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return _FakeNetworkStream(_redirect_response(302, location))

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert connections == [("93.184.216.34", 443)]
    assert not list(tmp_path.iterdir())


async def test_same_host_redirect_rejects_dns_rebinding(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    lookups = []
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        lookups.append(host)
        address = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
        return [_dns_answer(address, port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return _FakeNetworkStream(_redirect_response(302, "/another.pdf"))

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert "non-public" in result.error
    assert lookups == ["papers.example.org", "papers.example.org"]
    assert connections == [("93.184.216.34", 443)]
    assert not list(tmp_path.iterdir())


async def test_redirect_loop_is_bounded(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    lookups = []
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        lookups.append(host)
        return [_dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        return _FakeNetworkStream(_redirect_response(302, "/file.pdf"))

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert "redirect" in result.error.lower()
    assert len(lookups) == len(connections) == download_service._MAX_REDIRECTS + 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", [httpcore.ConnectError, httpcore.ConnectTimeout])
async def test_scimesh_falls_back_to_validated_dns_addresses(monkeypatch, tmp_path, failure):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    lookups = []
    connections = []
    stream = _FakeNetworkStream(
        b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
    )

    async def getaddrinfo(host, port, **kwargs):
        lookups.append((host, port))
        return [_dns_answer("2606:4700:4700::1111", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port, kwargs["timeout"]))
        if len(connections) == 1:
            raise failure("unreachable")
        return stream

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert Path(result.path).read_bytes() == b"%PDF-1.7"
    assert lookups == [("papers.example.org", 443)]
    assert [(host, port) for host, port, _ in connections] == [
        ("2606:4700:4700::1111", 443),
        ("93.184.216.34", 443),
    ]
    assert 0 < connections[0][2] <= settings.provider_timeout_seconds / 2
    assert 0 < connections[1][2] <= settings.provider_timeout_seconds
    assert stream.server_hostname == "papers.example.org"


async def test_slow_first_address_leaves_time_for_fallback(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.6)
    connections = []
    stream = _FakeNetworkStream(
        b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
    )

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer("2606:4700:4700::1111", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append(host)
        if len(connections) == 1:
            await asyncio.sleep(kwargs["timeout"])
            raise httpcore.ConnectTimeout("unreachable")
        return stream

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await asyncio.wait_for(download_one("arxiv", "2401.00001", {}), timeout=3)

    assert result.status == "ok"
    assert connections == ["2606:4700:4700::1111", "93.184.216.34"]


@pytest.mark.parametrize("failure", ["read_error", "timeout"])
async def test_header_failure_retries_next_validated_address(monkeypatch, tmp_path, failure):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.6)
    connections = []

    class FailedResponseStream(_FakeNetworkStream):
        async def read(self, max_bytes, timeout=None):
            if failure == "timeout":
                await asyncio.sleep(1)
            raise httpcore.ReadError("unreachable")

    failed_stream = FailedResponseStream(b"")
    success_stream = _FakeNetworkStream(
        b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
    )

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer("8.8.8.8", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append(host)
        return failed_stream if len(connections) == 1 else success_stream

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await asyncio.wait_for(download_one("arxiv", "2401.00001", {}), timeout=3)

    assert result.status == "ok"
    assert connections == ["8.8.8.8", "93.184.216.34"]
    assert failed_stream.server_hostname == success_stream.server_hostname == "papers.example.org"


async def test_all_addresses_timing_out_returns_error(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.6)
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer("8.8.8.8", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append(host)
        await asyncio.sleep(1)
        return _FakeNetworkStream(b"")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await asyncio.wait_for(download_one("arxiv", "2401.00001", {}), timeout=3)

    assert result.status == "error"
    assert "timed out" in result.error
    assert connections == ["8.8.8.8", "93.184.216.34"]
    assert not list(tmp_path.iterdir())


async def test_redirect_retries_only_each_hops_validated_addresses(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    lookups = []
    connections = []
    streams = [
        _FakeNetworkStream(_redirect_response(302, "https://pdfs.example.org/paper.pdf")),
        _FakeNetworkStream(
            b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n%PDF-1.7"
        ),
    ]

    async def getaddrinfo(host, port, **kwargs):
        lookups.append(host)
        addresses = {
            "papers.example.org": ["8.8.8.8", "93.184.216.34"],
            "pdfs.example.org": ["1.1.1.1", "8.8.4.4"],
        }
        return [_dns_answer(address, port) for address in addresses[host]]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append((host, port))
        if host in {"8.8.8.8", "1.1.1.1"}:
            raise httpcore.ConnectError("unreachable")
        return streams.pop(0)

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "ok"
    assert lookups == ["papers.example.org", "pdfs.example.org"]
    assert connections == [
        ("8.8.8.8", 443),
        ("93.184.216.34", 443),
        ("1.1.1.1", 443),
        ("8.8.4.4", 443),
    ]
    assert not streams


async def test_http_error_does_not_retry_other_addresses(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer("8.8.8.8", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append(host)
        return _FakeNetworkStream(
            b"HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert connections == ["8.8.8.8"]
    assert not list(tmp_path.iterdir())


async def test_all_validated_addresses_failing_returns_error(monkeypatch, tmp_path):
    _mock_scimesh_pdf(monkeypatch, tmp_path, "https://papers.example.org/file.pdf")
    connections = []

    async def getaddrinfo(host, port, **kwargs):
        return [_dns_answer("8.8.8.8", port), _dns_answer("93.184.216.34", port)]

    async def connect_tcp(self, host, port, **kwargs):
        connections.append(host)
        raise httpcore.ConnectError("unreachable")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect_tcp)

    result = await download_one("arxiv", "2401.00001", {})

    assert result.status == "error"
    assert connections == ["8.8.8.8", "93.184.216.34"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("allowed", [False, True])
async def test_academic_mcp_download_gate(monkeypatch, tmp_path, allowed):
    downloader = AsyncMock(return_value=str(tmp_path / "paper.pdf"))
    monkeypatch.setattr(settings, "academic_mcp_downloads_allowed", allowed)
    monkeypatch.setattr(academic_mcp_adapter, "download", downloader)
    monkeypatch.setattr(download_service, "_dest_dir", lambda: str(tmp_path))

    result = await download_one("pubmed", "32790614", {})

    if allowed:
        assert result.status == "ok"
        downloader.assert_awaited_once_with("pubmed", {}, "32790614", str(tmp_path))
    else:
        assert result.status == "error"
        assert "ACADEMIC_MCP_DOWNLOADS_ALLOWED" in result.error
        downloader.assert_not_awaited()


@pytest.mark.parametrize("allowed", [False, True])
async def test_academic_mcp_fulltext_gate(monkeypatch, allowed):
    reader = AsyncMock(return_value="extracted text")
    monkeypatch.setattr(settings, "academic_mcp_downloads_allowed", allowed)
    monkeypatch.setattr(academic_mcp_adapter, "read_fulltext", reader)

    if allowed:
        result = await read_fulltext("ieee", "12345", {"ieee": {"api_key": "key"}})
        assert result == "extracted text"
        reader.assert_awaited_once()
        assert reader.await_args.args[:3] == ("ieee", {"api_key": "key"}, "12345")
        assert Path(reader.await_args.args[3]).name == "fulltext"
    else:
        with pytest.raises(FulltextUnavailableError, match="ACADEMIC_MCP_DOWNLOADS_ALLOWED"):
            await read_fulltext("ieee", "12345", {"ieee": {"api_key": "key"}})
        reader.assert_not_awaited()


async def test_fulltext_gate_also_blocks_cached_pdfs(monkeypatch, tmp_path):
    cache_dir = tmp_path / "academic-search-service" / "fulltext"
    cache_dir.mkdir(parents=True)
    cached_pdf = cache_dir / "PMC123.pdf"
    cached_pdf.write_bytes(b"%PDF-1.7")
    reader = AsyncMock(return_value="extracted text")
    monkeypatch.setattr(settings, "academic_mcp_downloads_allowed", False)
    monkeypatch.setattr(academic_mcp_adapter, "read_fulltext", reader)
    monkeypatch.setattr(fulltext_service.tempfile, "gettempdir", lambda: str(tmp_path))

    with pytest.raises(FulltextUnavailableError, match="ACADEMIC_MCP_DOWNLOADS_ALLOWED"):
        await read_fulltext("pmc", "PMC123", {})

    reader.assert_not_awaited()
    assert cached_pdf.read_bytes() == b"%PDF-1.7"
