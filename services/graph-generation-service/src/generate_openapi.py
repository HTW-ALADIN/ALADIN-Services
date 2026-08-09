#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> Path:
    service_root = Path(__file__).parent.parent
    output_path = service_root / "graph-generation-service.openapi.json"
    output_path.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False))
    print(f"OpenAPI spec written to {output_path}")
    return output_path


if __name__ == "__main__":  # pragma: no cover
    main()
