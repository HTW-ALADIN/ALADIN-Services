"""Typer CLI mirroring the HTTP API 1:1 -- JSON in, JSON out.

Each subcommand is a thin wrapper around the same `core/*` service functions
the HTTP routes call; there is no CLI-specific business logic, and credentials
passed via `--credentials` go through the exact same Credential Resolver
validation as the HTTP path.
"""

import typer

from cli.commands import authors as authors_cmd
from cli.commands import download as download_cmd
from cli.commands import export as export_cmd
from cli.commands import graph as graph_cmd
from cli.commands import search as search_cmd

app = typer.Typer(name="academic-search", help="Unified academic search CLI (JSON in, JSON out).")

app.command("search")(search_cmd.search)
app.command("authors")(authors_cmd.authors)
app.command("export")(export_cmd.export)
app.command("download")(download_cmd.download)
app.command("graph")(graph_cmd.graph)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
