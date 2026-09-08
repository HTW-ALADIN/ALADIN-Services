from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter

from app.exceptions import GraphBackendError, GraphExportError
from app.exporters import export_isolated as export_graph
from app.routing import execute_isolated as execute_request
from app.schemas import GraphGenerationRequest, validate_graph_size
from graph_safety.limits import LIMITS, ResourceLimitError

REQUEST_ADAPTER: TypeAdapter[GraphGenerationRequest] = TypeAdapter(GraphGenerationRequest)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graph-generation-service")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate a graph from a JSON request")
    generate.add_argument("request", help="JSON request, path to a JSON file, or '-' for stdin")
    return parser


def _read_request(source: str) -> str:
    if source == "-":
        raw = sys.stdin.buffer.read(LIMITS.request_bytes + 1)
        if len(raw) > LIMITS.request_bytes:
            raise ResourceLimitError("request body exceeds the byte limit")
        return raw.decode()
    if source.lstrip().startswith(("{", "[")):
        if len(source.encode()) > LIMITS.request_bytes:
            raise ResourceLimitError("request body exceeds the byte limit")
        return source
    path = Path(source)
    if path.is_file():
        with path.open("rb") as file:
            raw = file.read(LIMITS.request_bytes + 1)
        if len(raw) > LIMITS.request_bytes:
            raise ResourceLimitError("request body exceeds the byte limit")
        return raw.decode()
    return source


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
    except (GraphBackendError, GraphExportError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    if isinstance(exported.content, bytes):
        if exported.media_type == "application/json":
            print(exported.content.decode())
            return 0
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
