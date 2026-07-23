"""Full-text extraction (as opposed to raw PDF download) — delegates to
academic-mcp's `read_paper`, which returns extracted plain text where the
underlying searcher supports it. scimesh has no equivalent, so this is only
available for academic-mcp-backed providers.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from adapters import academic_mcp_adapter
from core.credentials import resolve_credentials
from core.identifiers import UnsafePaperIdError, assert_safe_paper_id
from core.provider_registry import get_provider_spec


class FulltextUnavailableError(Exception):
    pass


async def read_fulltext(
    provider: str, paper_id: str, credentials: dict[str, dict[str, str]]
) -> str:
    try:
        assert_safe_paper_id(paper_id)
    except UnsafePaperIdError as exc:
        raise FulltextUnavailableError(f"unsafe_paper_id: {exc}") from exc

    spec = get_provider_spec(provider)
    if spec.backend != "academic_mcp":
        raise FulltextUnavailableError(
            f"Full-text extraction is only available for academic-mcp-backed "
            f"providers; '{provider}' is backed by {spec.backend}."
        )

    resolution = resolve_credentials(provider, credentials.get(provider))
    if not resolution.ok:
        raise FulltextUnavailableError("missing_credentials")

    dest_dir = str(Path(tempfile.gettempdir()) / "academic-search-service" / "fulltext")
    return await academic_mcp_adapter.read_fulltext(
        provider, resolution.credentials, paper_id, dest_dir
    )
