from __future__ import annotations

import asyncio
import json

import typer

from core.download_service import BatchSizeError, download_one, validate_batch_size


def download(
    items: str = typer.Option(..., help='JSON list of {"provider": ..., "paper_id": ...} objects'),
    credentials: str = typer.Option("{}", help="JSON object of {provider: {field: value}}"),
) -> None:
    """Download a bounded batch of papers; prints a DownloadResponse-shaped JSON object.

    Enforces the same DOWNLOAD_MAX_BATCH_SIZE bound as the HTTP API's
    /v1/download (see core/download_service.validate_batch_size) -- larger
    batches must be paginated client-side across multiple CLI invocations.
    """
    item_list = json.loads(items)
    try:
        validate_batch_size(len(item_list))
    except BatchSizeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    creds = json.loads(credentials)

    async def _run() -> list[dict]:
        results = await asyncio.gather(
            *[download_one(i["provider"], i["paper_id"], creds) for i in item_list]
        )
        return [
            {
                "provider": r.provider,
                "paper_id": r.paper_id,
                "status": r.status,
                "path": r.path,
                "error": r.error,
            }
            for r in results
        ]

    results = asyncio.run(_run())
    typer.echo(json.dumps({"results": results}, indent=2))
