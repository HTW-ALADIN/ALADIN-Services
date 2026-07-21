"""CLI interface for the edit-distance-service (mirrors noise-generation-service CLI pattern)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Unified CLI for edit distance algorithms (text and graph)."""


@cli.command(name="list", aliases=["ls"])
@click.option("--format", "-f", "fmt", default="json", type=click.Choice(["json", "table"]))
@click.option("--domain", "-d", default="text", type=click.Choice(["text", "graph", "all"]))
def list_algorithms(fmt: str, domain: str):
    """List all available algorithms and backends."""
    from src.main import TEXT_ALGORITHM_CATALOG, GED_ALGORITHM_CATALOG

    data = []
    if domain in ("text", "all"):
        data.extend(TEXT_ALGORITHM_CATALOG)
    if domain in ("graph", "all"):
        data.extend(GED_ALGORITHM_CATALOG)

    if fmt == "table":
        print(f"{'Algorithm':<25} {'Backend':<15} {'Result Type':<18} {'Families'}")
        print("-" * 100)
        for entry in data:
            alg = entry["algorithm"]
            backend = entry["backend"]
            rtype = entry.get("result_type", "N/A")
            families = "; ".join(entry.get("families", []))[:50]
            print(f"{alg:<25} {backend:<15} {rtype:<18} {families}")
        print(f"\nTotal: {len(data)} algorithm/backend combinations")
    else:
        print(json.dumps(data, indent=2))


@cli.command()
@click.option("--algorithm", "-a", required=True, help="Algorithm to use")
@click.option("--backend", "-b", default=None, help="Backend to use")
@click.option("--input-a", "-A", default=None, help="First input string (or use --inputs-file)")
@click.option("--input-b", "-B", default=None, help="Second input string")
@click.option("--inputs-file", "-f", type=click.Path(exists=True), help="JSON file with inputs array")
@click.option("--param", "-p", "params", multiple=True, help="Additional parameters (key=value)")
@click.option("--output", "-o", type=click.Path(), help="Output file (stdout if not specified)")
def compare(algorithm: str, backend: Optional[str], input_a: Optional[str], input_b: Optional[str],
            inputs_file: Optional[str], params: tuple[str], output: Optional[str]):
    """Compute edit distance for text pairs (local CLI)."""
    import httpx
    from src.main import _get_default_backend

    effective_backend = backend or _get_default_backend(algorithm)

    # Build inputs
    if inputs_file:
        with open(inputs_file) as f:
            raw_inputs = json.load(f)
    elif input_a and input_b:
        raw_inputs = [{"id": "pair-1", "a": input_a, "b": input_b}]
    else:
        click.echo("Error: provide either --input-a/--input-b or --inputs-file", err=True)
        sys.exit(1)

    # Parse params
    parsed_params = {}
    for p in params:
        if "=" in p:
            key, value = p.split("=", 1)
            # Try to parse as number
            try:
                parsed_params[key] = int(value)
            except ValueError:
                try:
                    parsed_params[key] = float(value)
                except ValueError:
                    if value.lower() in ("true", "false"):
                        parsed_params[key] = value.lower() == "true"
                    else:
                        parsed_params[key] = value

    request = {
        "algorithm": algorithm,
        "backend": effective_backend,
        "params": parsed_params,
        "inputs": raw_inputs,
    }

    # Try local server first, then direct computation
    try:
        resp = httpx.post("http://localhost:8000/v1/text/compare", json=request, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        # Fallback: direct computation
        from src.text import compute_text
        from src.models import InputPair
        inputs = [InputPair(**inp) for inp in raw_inputs]
        try:
            results, result_type, compute_ms = compute_text(algorithm, effective_backend, inputs, parsed_params)
            result = {
                "algorithm": algorithm,
                "backend": effective_backend,
                "result_type": result_type,
                "results": [r.model_dump() for r in results],
                "meta": {"compute_time_ms": round(compute_ms, 2)},
            }
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    text = json.dumps(result, indent=2)
    if output:
        Path(output).write_text(text)
        click.echo(f"Result written to {output}")
    else:
        print(text)


@cli.command()
@click.option("--port", "-p", default=8000, type=int, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
def serve(port: int, host: str):
    """Start the HTTP server."""
    import uvicorn
    click.echo(f"Starting edit-distance-service on {host}:{port}")
    uvicorn.run("src.main:app", host=host, port=port, reload=False)


@cli.command(name="openapi")
@click.option("--output", "-o", type=click.Path(), help="Output file")
@click.option("--format", "-f", "fmt", default="json", type=click.Choice(["json"]))
def generate_openapi(output: Optional[str], fmt: str):
    """Generate OpenAPI specification."""
    from fastapi.openapi.utils import get_openapi
    from src.main import app

    spec = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    text = json.dumps(spec, indent=2)
    if output:
        Path(output).write_text(text)
        click.echo(f"OpenAPI spec written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    cli()