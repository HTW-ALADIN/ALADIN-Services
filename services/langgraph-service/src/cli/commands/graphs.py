from __future__ import annotations

import json
from pathlib import Path

import typer

import main as app_module
from core.dsl import GraphDefinition
from core.store import registry
from core.url_safety import UnsafeUrlError, assert_safe_url


def graph(
    action: str = typer.Argument(..., help="create|get|list|delete"),
    graph_id: str | None = typer.Argument(None, help="Graph id for get/delete"),
    file: str | None = typer.Option(
        None, "--file", help="Graph definition JSON file ('-' for stdin)"
    ),
) -> None:
    """Manage graph definitions; prints JSON."""
    app_module.ensure_runtime()
    if action == "create":
        if file is None:
            raise typer.BadParameter("--file is required for graph create")
        raw = typer.get_text_stream("stdin").read() if file == "-" else Path(file).read_text()
        payload = json.loads(raw)
        definition = GraphDefinition.model_validate(payload)
        for node in definition.nodes:
            if node.type == "http":
                try:
                    assert_safe_url(node.url)
                except UnsafeUrlError as exc:
                    raise typer.BadParameter(
                        f"http node {node.id!r} has unsafe URL: {exc}"
                    ) from exc
        stored = registry.create_graph(definition)
        typer.echo(
            json.dumps(
                {
                    "graph_id": stored.graph_id,
                    "name": stored.definition.name,
                    "created_at": stored.created_at,
                },
                indent=2,
            )
        )
    elif action == "get":
        if graph_id is None:
            raise typer.BadParameter("graph_id is required for graph get")
        stored = registry.get_graph(graph_id)
        if stored is None:
            raise typer.BadParameter(f"Unknown graph id {graph_id!r}.")
        typer.echo(
            json.dumps(
                {
                    "graph_id": stored.graph_id,
                    "name": stored.definition.name,
                    "created_at": stored.created_at,
                    "definition": stored.definition.model_dump(mode="json"),
                },
                indent=2,
            )
        )
    elif action == "list":
        typer.echo(
            json.dumps(
                {
                    "graphs": [
                        {
                            "graph_id": g.graph_id,
                            "name": g.definition.name,
                            "created_at": g.created_at,
                        }
                        for g in registry.list_graphs()
                    ]
                },
                indent=2,
            )
        )
    elif action == "delete":
        if graph_id is None:
            raise typer.BadParameter("graph_id is required for graph delete")
        if not registry.delete_graph(graph_id):
            raise typer.BadParameter(f"Unknown graph id {graph_id!r}.")
        typer.echo(json.dumps({"deleted": graph_id}, indent=2))
    else:
        raise typer.BadParameter(
            f"unknown graph action {action!r}; expected create|get|list|delete"
        )
