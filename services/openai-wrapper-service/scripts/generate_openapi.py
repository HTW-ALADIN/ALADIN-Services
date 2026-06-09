#!/usr/bin/env python
from __future__ import annotations

import json
import pathlib

from openai_wrapper_service.api import app

_script_dir = pathlib.Path(__file__).parent


def main() -> pathlib.Path:
    service_root = _script_dir.parent
    output_path = service_root / "openai-wrapper-service.openapi.json"

    output_path.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False))
    print(f"OpenAPI spec written to {output_path}")
    return output_path


if __name__ == "__main__":  # pragma: no cover
    main()
