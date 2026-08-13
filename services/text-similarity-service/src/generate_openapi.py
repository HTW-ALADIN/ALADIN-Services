"""Writes text-similarity-service.openapi.json at the service root.

Run via `make generate-openapi`.
"""

import json
from pathlib import Path

from src.main import app

if __name__ == "__main__":
    spec = app.openapi()
    out_path = Path(__file__).resolve().parent.parent / "text-similarity-service.openapi.json"
    out_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Wrote OpenAPI spec to {out_path}")
