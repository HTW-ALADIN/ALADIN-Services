from __future__ import annotations

from fastapi import APIRouter

from api.schemas.authors import (
    AuthorProviderResultSchema,
    AuthorSearchRequest,
    AuthorSearchResponse,
)
from core.author_search_service import run_author_search

router = APIRouter()


@router.post("/v1/authors/search", response_model=AuthorSearchResponse)
async def search_authors(request: AuthorSearchRequest) -> AuthorSearchResponse:
    outcome = await run_author_search(
        query=request.query,
        providers=request.providers,
        output=request.output,
        credentials=request.credentials,
        max_results=request.max_results,
        per_provider_max=request.per_provider_max,
        include_raw=request.include_raw,
    )

    return AuthorSearchResponse(
        authors=outcome.authors,
        papers=outcome.papers,
        per_provider={
            provider: AuthorProviderResultSchema(count=result.count, errors=result.errors)
            for provider, result in outcome.per_provider.items()
        },
        took_ms=outcome.took_ms,
    )
