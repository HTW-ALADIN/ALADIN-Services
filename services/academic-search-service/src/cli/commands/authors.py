from __future__ import annotations

import asyncio
import json

import typer

from core.author import AuthorQuery
from core.author_search_service import run_author_search


def authors(
    query: str = typer.Option(
        ...,
        help=(
            'JSON AuthorQuery, e.g. \'{"name": "Jane Smith"}\' or '
            '\'{"ids": {"orcid": "0000-0002-1825-0097"}}\''
        ),
    ),
    providers: str = typer.Option(..., help="Comma-separated provider names"),
    output: str = typer.Option("authors", help='"authors" or "papers"'),
    credentials: str = typer.Option("{}", help="JSON object of {provider: {field: value}}"),
    max_results: int = typer.Option(100),
    per_provider_max: int = typer.Option(50),
    include_raw: bool = typer.Option(False),
) -> None:
    """Search for authors by name/partial name/ID, or fetch papers by a
    matched author; prints an AuthorSearchResponse-shaped JSON object."""
    author_query = AuthorQuery.model_validate_json(query)
    provider_list = [p.strip() for p in providers.split(",") if p.strip()]
    creds = json.loads(credentials)

    outcome = asyncio.run(
        run_author_search(
            query=author_query,
            providers=provider_list,
            output=output,  # type: ignore[arg-type]
            credentials=creds,
            max_results=max_results,
            per_provider_max=per_provider_max,
            include_raw=include_raw,
        )
    )

    payload = {
        "authors": [a.model_dump(mode="json", exclude_none=True) for a in outcome.authors],
        "papers": [p.model_dump(mode="json", exclude_none=True) for p in outcome.papers],
        "per_provider": {
            provider: {"count": result.count, "errors": result.errors}
            for provider, result in outcome.per_provider.items()
        },
        "took_ms": outcome.took_ms,
    }
    typer.echo(json.dumps(payload, indent=2))
