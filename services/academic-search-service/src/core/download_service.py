"""Download Service: bounded-batch, synchronous full-text/PDF retrieval.

No job queue, no object storage -- files land in a container-local tmp
directory. Batches larger than `settings.download_max_batch_size` must be
paginated client-side across multiple calls (enforced by the API/CLI layer,
not here).
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from adapters import academic_mcp_adapter, scimesh_adapter
from config import settings
from core.credentials import resolve_credentials
from core.identifiers import UnsafePaperIdError, assert_safe_paper_id
from core.provider_registry import get_provider_spec
from core.url_safety import UnsafeUrlError, resolve_safe_url

Status = Literal["ok", "paywalled", "not_found", "error"]

_MAX_REDIRECTS = 5


class BatchSizeError(ValueError):
    """Raised when a download batch is empty or exceeds the configured bound."""


def validate_batch_size(item_count: int) -> None:
    """Shared bound-check used by both the HTTP API (api/schemas/download.py)
    and the CLI (cli/commands/download.py), so the two interfaces cannot
    silently diverge on what counts as an acceptable batch size.
    """
    if item_count == 0:
        raise BatchSizeError("items must not be empty")
    if item_count > settings.download_max_batch_size:
        raise BatchSizeError(
            f"Batch of {item_count} exceeds DOWNLOAD_MAX_BATCH_SIZE="
            f"{settings.download_max_batch_size}. Paginate this list "
            f"client-side across multiple download calls instead."
        )


@dataclass
class DownloadResult:
    provider: str
    paper_id: str
    status: Status
    path: str | None = None
    error: str | None = None


def _dest_dir() -> str:
    base = Path(tempfile.gettempdir()) / "academic-search-service" / "downloads"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


class _PinnedDownloadTransport(httpx.AsyncBaseTransport):
    def __init__(self, timeout: float) -> None:
        self._timeout = timeout
        self._transport = httpx.AsyncHTTPTransport(
            trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url, addresses = await resolve_safe_url(str(request.url), self._timeout)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout

        for index, address in enumerate(addresses):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise httpx.ConnectTimeout(
                    "Download connection attempts timed out", request=request
                )

            attempt_timeout = remaining / (len(addresses) - index)
            headers = httpx.Headers(request.headers)
            headers["Host"] = url.netloc.decode("ascii")
            extensions = dict(request.extensions)
            extensions["sni_hostname"] = url.raw_host.decode("ascii")
            extensions["timeout"] = {
                **extensions.get("timeout", {}),
                "connect": attempt_timeout,
            }
            pinned_request = httpx.Request(
                request.method,
                url.copy_with(host=address),
                headers=headers,
                stream=request.stream,
                extensions=extensions,
            )
            try:
                async with asyncio.timeout(attempt_timeout):
                    return await self._transport.handle_async_request(pinned_request)
            except TimeoutError as exc:
                if index == len(addresses) - 1:
                    raise httpx.TimeoutException(
                        "Download request timed out", request=request
                    ) from exc
            except (httpx.NetworkError, httpx.TimeoutException, httpx.RemoteProtocolError):
                if index == len(addresses) - 1:
                    raise

        raise httpx.ConnectError("No validated address available", request=request)

    async def aclose(self) -> None:
        await self._transport.aclose()


async def _download_via_scimesh(
    provider: str, paper_id: str, credentials: dict[str, str], dest_dir: str
) -> DownloadResult:
    paper = await scimesh_adapter.get(provider, credentials, paper_id)
    if paper is None:
        return DownloadResult(provider, paper_id, "not_found", error="paper not found")
    if not paper.pdf_url:
        status: Status = "ok" if paper.open_access else "paywalled"
        return DownloadResult(
            provider,
            paper_id,
            "paywalled" if status == "paywalled" else "not_found",
            error="no pdf_url available from provider",
        )

    dest_path = Path(dest_dir) / f"{provider}_{paper_id.replace('/', '_')}.pdf"
    try:
        async with httpx.AsyncClient(
            timeout=settings.provider_timeout_seconds,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            trust_env=False,
            transport=_PinnedDownloadTransport(settings.provider_timeout_seconds),
        ) as client:
            response = await client.get(paper.pdf_url)
            response.raise_for_status()
            dest_path.write_bytes(response.content)
        return DownloadResult(provider, paper_id, "ok", path=str(dest_path))
    except (UnsafeUrlError, httpx.InvalidURL, UnicodeError) as exc:
        return DownloadResult(provider, paper_id, "error", error=f"unsafe pdf_url: {exc}")
    except httpx.HTTPError as exc:
        return DownloadResult(provider, paper_id, "error", error=str(exc))


async def _download_via_academic_mcp(
    provider: str, paper_id: str, credentials: dict[str, str], dest_dir: str
) -> DownloadResult:
    # Unlike the scimesh path above, academic-mcp's searchers resolve and fetch
    # the PDF URL entirely inside the vendored library (e.g.
    # `requests.get(provider_supplied_url)`), with no point at which this
    # service can intercept the URL to run it through `core/url_safety.py`
    # first. Because provider-supplied URLs are not fully trusted (the same
    # risk shape as caller-supplied URLs elsewhere in this service), this path
    # is gated behind an explicit operator opt-in (ACADEMIC_MCP_DOWNLOADS_ALLOWED)
    # and remains disabled by default; even when enabled, network-level egress
    # controls are still required (see the README's Security Disclaimer). The
    # scimesh path validates every URL and is unaffected by this gate.
    if not settings.academic_mcp_downloads_allowed:
        return DownloadResult(
            provider,
            paper_id,
            "error",
            error=(
                "academic_mcp downloads are disabled by default (SSRF gap: "
                "provider-supplied PDF URLs cannot be validated before fetch). "
                "Set ACADEMIC_MCP_DOWNLOADS_ALLOWED=true to enable, with egress "
                "controls in place."
            ),
        )
    try:
        path = await academic_mcp_adapter.download(provider, credentials, paper_id, dest_dir)
    except Exception as exc:  # noqa: BLE001
        return DownloadResult(provider, paper_id, "error", error=str(exc))

    if path.lower().startswith("error"):
        return DownloadResult(provider, paper_id, "error", error=path)
    return DownloadResult(provider, paper_id, "ok", path=path)


async def download_one(
    provider: str, paper_id: str, credentials: dict[str, dict[str, str]]
) -> DownloadResult:
    try:
        assert_safe_paper_id(paper_id)
    except UnsafePaperIdError as exc:
        return DownloadResult(provider, paper_id, "error", error=f"unsafe_paper_id: {exc}")

    try:
        spec = get_provider_spec(provider)
    except KeyError:
        return DownloadResult(provider, paper_id, "error", error="unknown_provider")

    resolution = resolve_credentials(provider, credentials.get(provider))
    if not resolution.ok:
        return DownloadResult(provider, paper_id, "error", error="missing_credentials")

    dest_dir = _dest_dir()
    if spec.backend == "scimesh":
        return await _download_via_scimesh(provider, paper_id, resolution.credentials, dest_dir)
    return await _download_via_academic_mcp(provider, paper_id, resolution.credentials, dest_dir)
