"""SageMath Wrapper CLI — dynamically registered from registry YAML files."""

import json
import os
import sys

import typer

from src.registry.dispatcher import execute_operation
from src.registry.loader import OperationSpec, load_registry

# CLI name overrides for backward compatibility with existing tests.
_CLI_NAME_OVERRIDES = {
    "maxima.evaluate": "eval",
}

app = typer.Typer()


def _register_command(
    group_app: typer.Typer,
    cmd_name: str,
    op: OperationSpec,
) -> None:
    """Register a single CLI command on *group_app* for *op*."""

    def _handler(payload: str = typer.Option("{}", "--payload", help="JSON payload for the operation"),
                 spec_file: str = typer.Option(None, "--spec-file", help="JSON spec file path")) -> None:
        if spec_file is not None:
            with open(spec_file) as f:
                payload_data = json.load(f)
        else:
            payload_data = json.loads(payload)
        result = execute_operation(op, payload_data)
        if not result["ok"]:
            print(f"Error: {result['error']}", file=sys.stderr)
            raise typer.Exit(1)
        json.dump(result["result"], sys.stdout, indent=2, default=str)
        print()

    _handler.__name__ = cmd_name
    _handler.__qualname__ = cmd_name
    group_app.command(name=cmd_name, help=op.summary)(_handler)


def _register_commands(app: typer.Typer, operations: list[OperationSpec]) -> None:
    """Register CLI subcommands for every *operations* on *app*."""
    groups: dict[str, typer.Typer] = {}

    for op in operations:
        parts = op.id.split(".", 1)
        group_name = parts[0]
        cmd_name = _CLI_NAME_OVERRIDES.get(op.id, parts[1] if len(parts) > 1 else op.id)
        if group_name not in groups:
            group_app = typer.Typer()
            groups[group_name] = group_app
            app.add_typer(group_app, name=group_name, help=group_name)
        _register_command(groups[group_name], cmd_name, op)


@app.command()
def serve():
    """Start the SageMath wrapper HTTP server."""
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)


# Load all registry YAMLs and register CLI commands dynamically
_registry_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "registry"
)
_operations = load_registry(_registry_path)
_register_commands(app, _operations)


if __name__ == "__main__":
    app()