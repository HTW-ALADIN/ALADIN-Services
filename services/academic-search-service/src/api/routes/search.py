from __future__ import annotations

from fastapi import APIRouter

from api.schemas.search import (
    DedupClusterSchema,
    DedupReportSchema,
    ProviderResultSchema,
    SearchRequest,
    SearchResponse,
)
from core.search_service import run_search

router = APIRouter()


@router.post("/v1/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    outcome = await run_search(
        query=request.query,
        providers=request.providers,
        credentials=request.credentials,
        max_results=request.max_results,
        per_provider_max=request.per_provider_max,
        dedup_enabled=request.dedup.enabled,
        dedup_strategy=request.dedup.strategy,
        include_raw=request.include_raw,
    )

    dedup_report = None
    if outcome.dedup_report is not None:
        dedup_report = DedupReportSchema(
            input_count=outcome.dedup_report.input_count,
            output_count=outcome.dedup_report.output_count,
            duplicates_removed=outcome.dedup_report.duplicates_removed,
            clusters=[
                DedupClusterSchema(
                    canonical_id=c.canonical_id,
                    match_tier=c.match_tier,
                    members=[{"id": m.id, "provider": m.provider} for m in c.members],
                )
                for c in outcome.dedup_report.clusters
            ],
            by_tier=outcome.dedup_report.by_tier,
            by_provider_pair=outcome.dedup_report.by_provider_pair,
        )

    return SearchResponse(
        papers=outcome.papers,
        per_provider={
            provider: ProviderResultSchema(count=result.count, errors=result.errors)
            for provider, result in outcome.per_provider.items()
        },
        dedup_report=dedup_report,
        took_ms=outcome.took_ms,
    )
