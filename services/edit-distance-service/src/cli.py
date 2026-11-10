"""Click-based CLI for the Edit Distance Service.

Mirrors every REST endpoint as a CLI subcommand.
Connects to a running instance (default: http://localhost:8000).
"""

import json
import sys
from typing import Any

import click
import requests

DEFAULT_BASE = "http://localhost:8000"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _request(method: str, path: str, base: str, **kwargs) -> dict[str, Any]:
    url = f"{base.rstrip('/')}{path}"
    try:
        resp = requests.request(method, url, **kwargs, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        click.echo(
            f"Error: Cannot connect to {base}. Is the service running?", err=True
        )
        sys.exit(1)
    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:  # noqa: BLE001
            detail = {"detail": str(e)}
        click.echo(json.dumps(detail, indent=2), err=True)
        sys.exit(1)


def _output(data: Any) -> None:
    """Pretty-print JSON output."""
    click.echo(json.dumps(data, indent=2, default=str))


def _parse_params(items: tuple[str, ...]) -> dict[str, Any]:
    """Parse --param/-p arguments into a JSON-compatible dict.

    Each item is either:
      - Full JSON:  ``{"mode": "exact", "timeout_ms": 5000}``
      - Shorthand:  ``mode=exact``

    Shorthand automatically converts ``true``/``false``/``null`` and
    numeric strings to their JSON types.
    """
    result: dict[str, Any] = {}
    for item in items:
        # Try full JSON first
        stripped = item.strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                if not isinstance(parsed, dict):
                    click.echo(
                        f"Error: JSON param must be an object, got: {stripped}",
                        err=True,
                    )
                    sys.exit(1)
                result.update(parsed)
            except json.JSONDecodeError as e:
                click.echo(f"Error: Invalid JSON param: {e}", err=True)
                sys.exit(1)
        elif "=" in stripped:
            key, val = stripped.split("=", 1)
            val = _coerce_shorthand(val)
            result[key] = val
        else:
            click.echo(
                f"Error: param '{item}' must be key=value or a JSON object", err=True
            )
            sys.exit(1)
    return result


def _coerce_shorthand(val: str) -> Any:
    lower = val.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


# ─── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
@click.option(
    "--base",
    "-b",
    default=DEFAULT_BASE,
    show_default=True,
    envvar="EDIT_DISTANCE_BASE_URL",
    help="Base URL of the running edit-distance-service.",
)
@click.pass_context
def cli(ctx: click.Context, base: str) -> None:
    """Edit Distance Service CLI.

    Mirrors all REST API endpoints. Point --base at a running instance
    (default http://localhost:8000) to list algorithms, compute distances, etc.
    """
    ctx.ensure_object(dict)
    ctx.obj["base"] = base


# ─── health ───────────────────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check service health."""
    data = _request("GET", "/health", ctx.obj["base"])
    _output(data)


# ─── list-text ────────────────────────────────────────────────────────────────


@cli.command(name="list-text")
@click.pass_context
def list_text(ctx: click.Context) -> None:
    """List all text algorithm/backend combinations."""
    data = _request("GET", "/v1/text/algorithms", ctx.obj["base"])
    _output(data)


# ─── list-graphs ──────────────────────────────────────────────────────────────


@cli.command(name="list-graphs")
@click.pass_context
def list_graphs(ctx: click.Context) -> None:
    """List all graph algorithm/backend/method combinations."""
    data = _request("GET", "/v1/graphs/algorithms", ctx.obj["base"])
    _output(data)


# ─── text-distance ────────────────────────────────────────────────────────────


@cli.command(name="text-distance")
@click.argument("algorithm")
@click.option(
    "--backend", "-b", default=None, help="Backend library (default: auto-select)."
)
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    help=(
        'JSON param value, e.g. -p "{"mode": "exact"}" '
        "or shorthand -p mode=exact. "
        "Shorthand converts true/false/null and numbers to their JSON types."
    ),
)
@click.option(
    "--input-file",
    "-f",
    type=click.Path(exists=True),
    help="JSON file with inputs array. Overrides inline --input.",
)
@click.option(
    "--input",
    "-i",
    "inline_inputs",
    multiple=True,
    help=(
        'Inline input as JSON, e.g. -i \'{"id":"p1","a":"kitten","b":"sitting"}\'. '
        "Can be repeated for batching."
    ),
)
@click.pass_context
def text_distance(
    ctx: click.Context,
    algorithm: str,
    backend: str | None,
    params: tuple[str, ...],
    input_file: str | None,
    inline_inputs: tuple[str, ...],
) -> None:
    """Compute text edit distance for one or more input pairs.

    ALGORITHM is one of the algorithms listed by list-text (e.g. levenshtein).

    Provide inputs either via --input-file (JSON array) or one or more
    --input / -i options. If neither is given, a minimal example is used.

    Parameters can be passed as:
      -p '{"mode":"exact","timeout_ms":5000}'   (full JSON)
      -p mode=exact -p timeout_ms=5000               (shorthand)
    """
    payload: dict[str, Any] = {"algorithm": algorithm}
    if backend:
        payload["backend"] = backend

    payload["params"] = _parse_params(params)

    if input_file:
        with open(input_file, encoding="utf-8") as fh:
            payload["inputs"] = json.load(fh)
    elif inline_inputs:
        payload["inputs"] = [json.loads(i) for i in inline_inputs]
    else:
        # Default minimal example
        payload["inputs"] = [{"id": "p1", "a": "kitten", "b": "sitting"}]

    data = _request("POST", "/v1/text/distance", ctx.obj["base"], json=payload)
    _output(data)


# ─── ged-distance ─────────────────────────────────────────────────────────────


@cli.command(name="ged-distance")
@click.argument("algorithm")
@click.option(
    "--backend", "-b", default=None, help="Backend library (default: auto-select)."
)
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    help=(
        'JSON param value, e.g. -p "{"mode": "exact"}" '
        "or shorthand -p mode=exact. "
        "Shorthand converts true/false/null and numbers to their JSON types."
    ),
)
@click.option(
    "--graph-file",
    "-f",
    type=click.Path(exists=True),
    help="JSON file with graphs array. Overrides inline --graph.",
)
@click.option(
    "--graph",
    "-g",
    "inline_graphs",
    multiple=True,
    help=(
        'Inline graph pair as JSON, e.g. -g \'{"id":"p1","g1":{"nodes":[...],"edges":[...]},'
        '"g2":{"nodes":[...],"edges":[...]}}\'. Can be repeated for batching.'
    ),
)
@click.pass_context
def ged_distance(
    ctx: click.Context,
    algorithm: str,
    backend: str | None,
    params: tuple[str, ...],
    graph_file: str | None,
    inline_graphs: tuple[str, ...],
) -> None:
    """Compute graph edit distance for one or more graph pairs.

    ALGORITHM is one of the algorithms listed by list-graphs (e.g. ged_astar).

    Provide graphs either via --graph-file (JSON array) or one or more
    --graph / -g options. If neither is given, a minimal example is used.

    Parameters can be passed as:
      -p '{"mode":"exact","timeout_ms":5000}'   (full JSON)
      -p mode=exact -p timeout_ms=5000               (shorthand)
    """
    payload: dict[str, Any] = {"algorithm": algorithm}
    if backend:
        payload["backend"] = backend

    payload["params"] = _parse_params(params)

    if graph_file:
        with open(graph_file, encoding="utf-8") as fh:
            payload["graphs"] = json.load(fh)
    elif inline_graphs:
        payload["graphs"] = [json.loads(g) for g in inline_graphs]
    else:
        # Default minimal example
        payload["graphs"] = [
            {
                "id": "p1",
                "g1": {
                    "nodes": [{"id": "A"}, {"id": "B"}],
                    "edges": [{"source": "A", "target": "B"}],
                },
                "g2": {
                    "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                    "edges": [
                        {"source": "A", "target": "B"},
                        {"source": "B", "target": "C"},
                    ],
                },
            }
        ]

    data = _request("POST", "/v1/graphs/distance", ctx.obj["base"], json=payload)
    _output(data)


if __name__ == "__main__":
    cli()
