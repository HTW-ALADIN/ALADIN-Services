from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from core.paper import Paper

ExportFormat = Literal["bibtex", "ris", "csv", "json"]


class ExportRequest(BaseModel):
    """Exports operate on an inline list of canonical papers.

    This service holds no persistent paper store (deliberately, per the
    repo-integration plan's "no new infra" decision), so there is no
    `paper_ids` lookup path -- callers pass back the `papers` array they
    previously received from `/v1/search` or `/v1/graph`.
    """

    papers: list[Paper]
    format: ExportFormat
