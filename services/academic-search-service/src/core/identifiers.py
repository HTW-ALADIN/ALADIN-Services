"""Safety checks for caller-supplied paper identifiers.

`paper_id` values are forwarded into backend libraries (scimesh, academic-mcp)
that -- for several academic-mcp searchers -- build a filesystem download path
directly from the identifier (e.g. `os.path.join(save_path, f"{paper_id}.pdf")`).
Since legitimate identifiers legitimately contain `/` (DOIs such as
`10.1101/2020.01.01.123456`, IACR ids such as `2009/101`), this cannot simply
reject all path separators -- instead it rejects the specific patterns that
enable path traversal or absolute-path escapes (`..` segments, a leading `/`
or `\\`, backslashes, and null bytes).
"""

from __future__ import annotations


class UnsafePaperIdError(ValueError):
    """Raised when a `paper_id` could escape the intended download directory."""


def assert_safe_paper_id(paper_id: str) -> None:
    if not paper_id or not paper_id.strip():
        raise UnsafePaperIdError("paper_id must not be empty")
    if "\x00" in paper_id:
        raise UnsafePaperIdError("paper_id must not contain null bytes")
    if paper_id.startswith("/") or paper_id.startswith("\\"):
        raise UnsafePaperIdError("paper_id must not be an absolute path")
    if "\\" in paper_id:
        raise UnsafePaperIdError("paper_id must not contain backslashes")
    if any(segment in ("..", ".") for segment in paper_id.split("/")):
        raise UnsafePaperIdError("paper_id must not contain path traversal segments")
