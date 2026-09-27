"""Typer CLI mirroring the HTTP API 1:1 -- JSON in, JSON out.

Each subcommand is a thin wrapper around the same `core/*` functions the HTTP
routes call; there is no CLI-specific business logic.
"""

import typer

from cli.commands import graphs as graphs_cmd
from cli.commands import runs as runs_cmd
from cli.commands import threads as threads_cmd

app = typer.Typer(
    name="langgraph-service", help="Generic LangGraph execution CLI (JSON in, JSON out)."
)

app.command("graph")(graphs_cmd.graph)
app.command("thread")(threads_cmd.thread)
app.command("run")(runs_cmd.run)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
