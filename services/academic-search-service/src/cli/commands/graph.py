from __future__ import annotations

import asyncio
import json

import typer

from config import settings
from core import graph_service


def graph(
    seeds: str = typer.Option(..., help='JSON list of {"provider": ..., "paper_id": ...} objects'),
    direction: str = typer.Option("both", help="citing | cited_by | both"),
    max_depth: int = typer.Option(settings.graph_max_depth_default),
    max_nodes_per_level: int = typer.Option(settings.graph_max_nodes_per_level_default),
    max_total_nodes: int = typer.Option(settings.graph_max_total_nodes_default),
    credentials: str = typer.Option("{}", help="JSON object of {provider: {field: value}}"),
) -> None:
    """Build a citation graph from seed papers.

    The HTTP API paginates this one BFS level per call; this CLI command
    loops internally over that same pagination until `done`, so CLI users get
    a single fully-expanded result for free.
    """
    seed_list = [(s["provider"], s["paper_id"]) for s in json.loads(seeds)]
    creds = json.loads(credentials)

    async def _run() -> dict:
        page = await graph_service.start(
            seeds=seed_list,
            direction=direction,  # type: ignore[arg-type]
            max_depth=max_depth,
            max_nodes_per_level=max_nodes_per_level,
            max_total_nodes=max_total_nodes,
            credentials=creds,
        )
        all_nodes = list(page.nodes)
        all_edges = list(page.edges)
        truncated = page.truncated

        while not page.done and page.cursor:
            page = await graph_service.advance(page.cursor, creds)
            all_nodes.extend(page.nodes)
            all_edges.extend(page.edges)
            truncated = truncated or page.truncated

        return {
            "nodes": [n.model_dump(mode="json", exclude_none=True) for n in all_nodes],
            "edges": [{"from": e.from_id, "to": e.to_id, "type": e.type} for e in all_edges],
            "depth_reached": page.depth_reached,
            "max_depth": max_depth,
            "truncated": truncated,
        }

    result = asyncio.run(_run())
    typer.echo(json.dumps(result, indent=2))
