"""Writes the OpenAPI spec(s) for the profile(s) at the service root.

The service builds as two images (``pytorch`` / ``cpu``) that differ in the
PyTorch-based algorithms they offer, so each gets its own spec file:

    text-similarity-service-pytorch.openapi.json
    text-similarity-service-cpu.openapi.json

Run ``make generate-openapi`` (both), or set ``SIMILARITY_PROFILE`` for one.
"""

import importlib
import json
import os
from pathlib import Path


def generate(profile: str) -> None:
    import src.catalog as catalog
    import src.main as main

    os.environ["SIMILARITY_PROFILE"] = profile
    importlib.reload(catalog)  # re-reads SIMILARITY_PROFILE -> PROFILE
    importlib.reload(main)  # re-imports catalog profile + rebuilds app

    spec = main.app.openapi()
    out_path = Path(__file__).resolve().parent.parent / f"text-similarity-service-{profile}.openapi.json"
    out_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Wrote OpenAPI spec to {out_path}")


if __name__ == "__main__":
    target = os.environ.get("SIMILARITY_PROFILE")
    for p in (target,) if target else ("pytorch", "cpu"):
        generate(p)
