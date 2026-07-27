"""Download Service: bounded-batch, synchronous full-text/PDF retrieval.

No job queue, no object storage -- files land in a container-local tmp
directory. Batches larger than `settings.download_max_batch_size` must be
paginated client-side across multiple calls (enforced by the API/CLI layer,
not here).
"""

from __future__ import annotations

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
from core.url_safety import UnsafeUrlError, assert_safe_url

Status = Literal["ok", "paywalled", "not_found", "error"]


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

    try:
        assert_safe_url(paper.pdf_url)
    except UnsafeUrlError as exc:
        return DownloadResult(provider, paper_id, "error", error=f"unsafe pdf_url: {exc}")

    dest_path = Path(dest_dir) / f"{provider}_{paper_id.replace('/', '_')}.pdf"
    try:
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.get(paper.pdf_url, follow_redirects=True)
            response.raise_for_status()
            dest_path.write_bytes(response.content)
        return DownloadResult(provider, paper_id, "ok", path=str(dest_path))
    except httpx.HTTPStatusError as exc:
        return DownloadResult(provider, paper_id, "error", error=str(exc))
    except httpx.HTTPError as exc:
        return DownloadResult(provider, paper_id, "error", error=str(exc))


async def _download_via_academic_mcp(
    provider: str, paper_id: str, credentials: dict[str, str], dest_dir: str
) -> DownloadResult:
    # NOTE (known SSRF-check gap): unlike the scimesh path above, academic-mcp's
    # searchers resolve and fetch the PDF URL entirely inside the vendored
    # library (e.g. `requests.get(provider_supplied_url)`), with no point at
    # which this service can intercept the URL to run it through
    # `core/url_safety.py` first. This is a real, currently-unmitigated gap
    # for academic-mcp-backed providers -- see the README's Security
    # Disclaimer -- until either the vendored library exposes a pluggable
    # HTTP transport or this adapter is rewritten to fetch PDFs itself.
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
