from __future__ import annotations

import asyncio
import json

import typer

from core.query import SearchQuery
from core.search_service import run_search


def search(
    query: str = typer.Option(
        ..., help='JSON SearchQuery, e.g. \'{"text": "graph neural networks"}\''
    ),
    providers: str = typer.Option(..., help="Comma-separated provider names"),
    credentials: str = typer.Option("{}", help="JSON object of {provider: {field: value}}"),
    max_results: int = typer.Option(100),
    per_provider_max: int = typer.Option(50),
    dedup: bool = typer.Option(False, help="Enable cross-provider deduplication"),
    dedup_strategy: str = typer.Option("auto"),
    include_raw: bool = typer.Option(False),
) -> None:
    """Search across multiple providers; prints a SearchResponse-shaped JSON object."""
    search_query = SearchQuery.model_validate_json(query)
    provider_list = [p.strip() for p in providers.split(",") if p.strip()]
    creds = json.loads(credentials)

    outcome = asyncio.run(
        run_search(
            query=search_query,
            providers=provider_list,
            credentials=creds,
            max_results=max_results,
            per_provider_max=per_provider_max,
            dedup_enabled=dedup,
            dedup_strategy=dedup_strategy,  # type: ignore[arg-type]
            include_raw=include_raw,
        )
    )

    payload = {
        "papers": [p.model_dump(mode="json", exclude_none=True) for p in outcome.papers],
        "per_provider": {
            provider: {"count": result.count, "errors": result.errors}
            for provider, result in outcome.per_provider.items()
        },
        "took_ms": outcome.took_ms,
    }
    typer.echo(json.dumps(payload, indent=2))
