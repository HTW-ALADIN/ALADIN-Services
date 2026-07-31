"""SageMath Wrapper CLI — dynamically registered from registry YAML files."""

import os

import typer

from src.cli.dynamic_commands import register_commands
from src.registry.loader import load_registry

app = typer.Typer()


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
register_commands(app, _operations)


if __name__ == "__main__":
    app()