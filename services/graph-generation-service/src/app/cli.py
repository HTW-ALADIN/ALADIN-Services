from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.exceptions import GraphBackendError, GraphExportError
from app.exporters import export_graph
from app.routing import execute_request
from app.schemas import GraphGenerationRequest, RequestParameterError, validate_graph_size

REQUEST_ADAPTER: TypeAdapter[GraphGenerationRequest] = TypeAdapter(GraphGenerationRequest)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graph-generation-service")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate a graph from a JSON request")
    generate.add_argument("request", help="JSON request, path to a JSON file, or '-' for stdin")
    return parser


def _read_request(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    if source.lstrip().startswith(("{", "[")):
        return source
    path = Path(source)
    return path.read_text() if path.is_file() else source


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = REQUEST_ADAPTER.validate_json(_read_request(str(args.request)))
        validate_graph_size(request)
        generated = execute_request(request)
        exported = export_graph(
            generated,
            output_format=request.output.format,
            labels=request.output.labels,
            resource_id="cli",
        )
    except (GraphBackendError, GraphExportError, OSError, RequestParameterError, ValidationError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    if exported.media_type == "application/json":
        print(json.dumps(exported.content))
    elif isinstance(exported.content, bytes):
        sys.stdout.buffer.write(exported.content)
    elif isinstance(exported.content, str):
        sys.stdout.write(exported.content)
    else:
        raise TypeError("Non-JSON CLI exports must contain text or bytes")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
