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


def generate(profile: str, *, disable_local_conceptnet: bool = False) -> None:
    import src.catalog as catalog
    import src.main as main

    os.environ["SIMILARITY_PROFILE"] = profile
    if disable_local_conceptnet:
        os.environ["SIMILARITY_DISABLE_LOCAL_CONCEPTNET"] = "true"
    else:
        os.environ.pop("SIMILARITY_DISABLE_LOCAL_CONCEPTNET", None)
    importlib.reload(catalog)  # re-reads SIMILARITY_PROFILE -> PROFILE (+ conceptnet flag)
    importlib.reload(main)  # re-imports catalog profile + rebuilds app

    suffix = "-hf" if disable_local_conceptnet else ""
    spec = main.app.openapi()
    out_path = Path(__file__).resolve().parent.parent / f"text-similarity-service-{profile}{suffix}.openapi.json"
    out_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Wrote OpenAPI spec to {out_path}")


if __name__ == "__main__":
    target = os.environ.get("SIMILARITY_PROFILE")
    if target:
        generate(target)
    else:
        generate("pytorch")
        generate("pytorch", disable_local_conceptnet=True)  # the light "hf" image
        generate("cpu")
