from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from core.paper import Paper
from export import export as export_papers


def export(
    input: str = typer.Option(
        "-", help="Path to a JSON file containing a SearchResponse-shaped object, or '-' for stdin"
    ),
    format: str = typer.Option(..., help="bibtex | ris | csv | json"),
) -> None:
    """Export a previously-fetched paper list to the requested format."""
    raw = sys.stdin.read() if input == "-" else Path(input).read_text()
    data = json.loads(raw)
    papers_data = data["papers"] if isinstance(data, dict) and "papers" in data else data
    papers = [Paper.model_validate(p) for p in papers_data]

    body = export_papers(papers, format)
    sys.stdout.buffer.write(body)
