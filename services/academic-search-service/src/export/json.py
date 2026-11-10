from __future__ import annotations

import json as json_module

from core.paper import Paper


def serialize(papers: list[Paper]) -> bytes:
    payload = [p.model_dump(mode="json", exclude_none=True) for p in papers]
    return json_module.dumps(payload, indent=2).encode("utf-8")
