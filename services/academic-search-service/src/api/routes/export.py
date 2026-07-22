from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from api.schemas.export import ExportRequest
from export import export as export_papers

router = APIRouter()

_MEDIA_TYPES = {
    "bibtex": "application/x-bibtex",
    "ris": "application/x-research-info-systems",
    "csv": "text/csv",
    "json": "application/json",
}


@router.post("/v1/export")
async def export_endpoint(request: ExportRequest) -> Response:
    body = export_papers(request.papers, request.format)
    return Response(content=body, media_type=_MEDIA_TYPES[request.format])
