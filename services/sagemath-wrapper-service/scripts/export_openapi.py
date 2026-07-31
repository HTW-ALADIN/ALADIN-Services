#!/usr/bin/env python
"""Export the FastAPI app's OpenAPI spec as a YAML file."""

import argparse
import sys
from pathlib import Path

# Ensure src/ is importable when run as a script
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root))

import yaml
from src.api.main import app


def main():
    parser = argparse.ArgumentParser(description="Export OpenAPI spec")
    parser.add_argument("--out", default="openapi/openapi.yaml", help="Output path")
    args = parser.parse_args()

    spec = app.openapi()
    with open(args.out, "w") as f:
        yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
    print(f"OpenAPI spec written to {args.out}")


if __name__ == "__main__":
    main()