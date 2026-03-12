#!/usr/bin/env python
"""
Generate the OpenAPI spec for the FermentALADIN API and write it to disk.

Usage:
    uv run python src/generate_openapi.py

Output:
    fermentaladin-service.openapi.json  (in the service root directory)
"""

import json
import pathlib
import sys

# Ensure src/ is on the path when this script is run from the service root.
_src_dir = pathlib.Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from api import app  # noqa: E402

_service_root = _src_dir.parent
_output_path = _service_root / "fermentaladin-service.openapi.json"

spec = app.openapi()
_output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
print(f"OpenAPI spec written to {_output_path}")
