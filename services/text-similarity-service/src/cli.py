"""Click-based CLI for the Text Similarity Service.

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
        click.echo(f"Error: Cannot connect to {base}. Is the service running?", err=True)
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
      - Full JSON:  ``{"variant": "jaro", "score_cutoff": 80}``
      - Shorthand:  ``variant=jaro``

    Shorthand automatically converts ``true``/``false``/``null`` and
    numeric strings to their JSON types.
    """
    result: dict[str, Any] = {}
    for item in items:
        stripped = item.strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                if not isinstance(parsed, dict):
                    click.echo(f"Error: JSON param must be an object, got: {stripped}", err=True)
                    sys.exit(1)
                result.update(parsed)
            except json.JSONDecodeError as e:
                click.echo(f"Error: Invalid JSON param: {e}", err=True)
                sys.exit(1)
        elif "=" in stripped:
            key, val = stripped.split("=", 1)
            result[key] = _coerce_shorthand(val)
        else:
            click.echo(f"Error: param '{item}' must be key=value or a JSON object", err=True)
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


def _load_inputs(input_file: str | None, inline_inputs: tuple[str, ...]) -> list[Any]:
    """Load the inputs array from --input-file, inline --input, or a default."""
    if input_file:
        with open(input_file, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else [data]
    if inline_inputs:
        return [json.loads(i) for i in inline_inputs]
    return []  # endpoint requires at least one input


# ─── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
@click.option(
    "--base",
    "-b",
    default=DEFAULT_BASE,
    show_default=True,
    envvar="TEXT_SIMILARITY_BASE_URL",
    help="Base URL of the running text-similarity-service.",
)
@click.pass_context
def cli(ctx: click.Context, base: str) -> None:
    """Text Similarity Service CLI.

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


# ─── list-algorithms ──────────────────────────────────────────────────────────


@cli.command(name="list-algorithms")
@click.pass_context
def list_algorithms(ctx: click.Context) -> None:
    """List all algorithm/backend combinations."""
    data = _request("GET", "/v1/text/algorithms", ctx.obj["base"])
    _output(data)


# ─── distance (similarity) ────────────────────────────────────────────────────


@cli.command(name="distance")
@click.argument("algorithm")
@click.option("--backend", "-B", default=None, help="Backend library (default: auto-selected).")
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    help=(
        'JSON param value, e.g. -p "{"variant": "jaro"}" '
        "or shorthand -p variant=jaro. "
        "Shorthand converts true/false/null and numbers to their JSON types."
    ),
)
@click.option(
    "--input-file",
    "-f",
    type=click.Path(exists=True),
    help="JSON file with the inputs array. Overrides inline --input.",
)
@click.option(
    "--input",
    "-i",
    "inline_inputs",
    multiple=True,
    help=('Inline input as JSON, e.g. -i \'{"id":"p1","a":"kitten","b":"sitting"}\'. Can be repeated for batching.'),
)
@click.pass_context
def distance(
    ctx: click.Context,
    algorithm: str,
    backend: str | None,
    params: tuple[str, ...],
    input_file: str | None,
    inline_inputs: tuple[str, ...],
) -> None:
    """Compute text similarity for one or more text pairs.

    ALGORITHM is one of the algorithms listed by list-algorithms
    (e.g. levenshtein). Inputs use the shape {"id", "a", "b"} and are
    provided via --input-file, one or more --input/-i options, or a
    minimal default example. When --backend is omitted the default
    backend is auto-selected.
    """
    payload: dict[str, Any] = {"algorithm": algorithm}
    if backend:
        payload["backend"] = backend
    payload["params"] = _parse_params(params)

    inputs = _load_inputs(input_file, inline_inputs)
    if not inputs:
        inputs = [{"id": "p1", "a": "kitten", "b": "sitting"}]
    payload["inputs"] = inputs

    data = _request("POST", "/v1/text/distance", ctx.obj["base"], json=payload)
    _output(data)


# ─── retrieval ────────────────────────────────────────────────────────────────


@cli.command(name="retrieval")
@click.argument("algorithm")
@click.option("--backend", "-B", default=None, help="Backend library (default: auto-selected).")
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    help=(
        'JSON param value, e.g. -p "{"limit": 3}" '
        "or shorthand -p limit=3. "
        "Shorthand converts true/false/null and numbers to their JSON types."
    ),
)
@click.option(
    "--input-file",
    "-f",
    type=click.Path(exists=True),
    help="JSON file with the inputs array. Overrides inline --input.",
)
@click.option(
    "--input",
    "-i",
    "inline_inputs",
    multiple=True,
    help=('Inline input as JSON, e.g. -i \'{"id":"q1","query":"kitten","candidates":["sitting","kitchen","kitten"]}\'. Can be repeated.'),
)
@click.pass_context
def retrieval(
    ctx: click.Context,
    algorithm: str,
    backend: str | None,
    params: tuple[str, ...],
    input_file: str | None,
    inline_inputs: tuple[str, ...],
) -> None:
    """Rank query candidates for one or more retrieval queries.

    ALGORITHM is one of the algorithms listed by list-algorithms
    (e.g. fuzzy_extract). Inputs use the shape {"id", "query", "candidates"}
    and are provided via --input-file, one or more --input/-i options, or a
    minimal default example.
    """
    payload: dict[str, Any] = {"algorithm": algorithm}
    if backend:
        payload["backend"] = backend
    payload["params"] = _parse_params(params)

    inputs = _load_inputs(input_file, inline_inputs)
    if not inputs:
        inputs = [{"id": "q1", "query": "kitten", "candidates": ["sitting", "kitchen", "kitten"]}]
    payload["inputs"] = inputs

    data = _request("POST", "/v1/text/retrieval", ctx.obj["base"], json=payload)
    _output(data)


# ─── lexical ──────────────────────────────────────────────────────────────────


@cli.command(name="lexical")
@click.argument("algorithm")
@click.option("--backend", "-B", default=None, help="Backend library (default: auto-selected).")
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    help='JSON param value, e.g. -p \'{"lang": "eng"}\' or shorthand -p lang=eng.',
)
@click.option(
    "--input-file",
    "-f",
    type=click.Path(exists=True),
    help="JSON file with the inputs array. Overrides inline --input.",
)
@click.option(
    "--input",
    "-i",
    "inline_inputs",
    multiple=True,
    help=('Inline input as JSON, e.g. -i \'{"id":"w1","word":"dog"}\'. Can be repeated for batching.'),
)
@click.pass_context
def lexical(
    ctx: click.Context,
    algorithm: str,
    backend: str | None,
    params: tuple[str, ...],
    input_file: str | None,
    inline_inputs: tuple[str, ...],
) -> None:
    """Look up lexical relations for one or more words.

    ALGORITHM is one of the algorithms listed by list-algorithms
    (e.g. synonym). Inputs use the shape {"id", "word"} and are provided via
    --input-file, one or more --input/-i options, or a minimal default example.
    """
    payload: dict[str, Any] = {"algorithm": algorithm}
    if backend:
        payload["backend"] = backend
    payload["params"] = _parse_params(params)

    inputs = _load_inputs(input_file, inline_inputs)
    if not inputs:
        inputs = [{"id": "w1", "word": "dog"}]
    payload["inputs"] = inputs

    data = _request("POST", "/v1/text/lexical", ctx.obj["base"], json=payload)
    _output(data)


if __name__ == "__main__":
    cli()
