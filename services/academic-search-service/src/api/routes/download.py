from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from api.schemas.download import (
    DownloadRequest,
    DownloadResponse,
    DownloadResultSchema,
    FulltextResponse,
)
from core.download_service import download_one
from core.fulltext_service import FulltextUnavailableError, read_fulltext

router = APIRouter()


@router.post("/v1/download", response_model=DownloadResponse)
async def download(request: DownloadRequest) -> DownloadResponse:
    results = await asyncio.gather(
        *[download_one(item.provider, item.paper_id, request.credentials) for item in request.items]
    )
    return DownloadResponse(
        results=[
            DownloadResultSchema(
                provider=r.provider,
                paper_id=r.paper_id,
                status=r.status,
                path=r.path,
                error=r.error,
            )
            for r in results
        ]
    )


@router.get("/v1/fulltext", response_model=FulltextResponse)
async def fulltext(provider: str, paper_id: str, api_key: str | None = None) -> FulltextResponse:
    credentials = {provider: {"api_key": api_key}} if api_key else {}
    try:
        text = await read_fulltext(provider, paper_id, credentials=credentials)
    except FulltextUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FulltextResponse(provider=provider, paper_id=paper_id, text=text)
