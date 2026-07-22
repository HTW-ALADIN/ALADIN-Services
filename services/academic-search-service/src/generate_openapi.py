"""Writes academic-search-service.openapi.json at the service root.

Run via `make generate-openapi` (`uv run python src/generate_openapi.py`).
"""

import json
from pathlib import Path

from main import app

if __name__ == "__main__":
    spec = app.openapi()
    out_path = Path(__file__).resolve().parent.parent / "academic-search-service.openapi.json"
    out_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Wrote OpenAPI spec to {out_path}")
