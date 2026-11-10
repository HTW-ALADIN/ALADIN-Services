"""Opaque, HMAC-signed cursor for the paginated /v1/graph endpoint.

The service holds no per-graph state between calls: the entire BFS frontier,
visited set, depth, and running node total are encoded into the cursor itself
and signed with `GRAPH_CURSOR_SECRET` so a caller cannot tamper with them
(e.g. to skip depth limits or inflate `max_total_nodes`). This keeps citation
graph pagination infra-free (no Redis, no job table) and safe to scale
horizontally across replicas.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any

_SIG_LEN = 32  # sha256 digest size


class InvalidCursorError(ValueError):
    """Raised when a cursor fails signature verification or is malformed."""


@dataclass(frozen=True)
class GraphCursorState:
    seeds: tuple[str, ...]
    direction: str
    max_depth: int
    max_nodes_per_level: int
    max_total_nodes: int
    frontier: tuple[str, ...]
    visited: tuple[str, ...]
    depth_reached: int
    total_nodes_emitted: int
    dedup_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _sign(secret: str, payload_b64: bytes) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload_b64, hashlib.sha256).digest()


def encode_cursor(secret: str, state: GraphCursorState) -> str:
    payload = json.dumps(
        {
            "seeds": list(state.seeds),
            "direction": state.direction,
            "max_depth": state.max_depth,
            "max_nodes_per_level": state.max_nodes_per_level,
            "max_total_nodes": state.max_total_nodes,
            "frontier": list(state.frontier),
            "visited": list(state.visited),
            "depth_reached": state.depth_reached,
            "total_nodes_emitted": state.total_nodes_emitted,
            "dedup_enabled": state.dedup_enabled,
            "extra": state.extra,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload)
    signature = _sign(secret, payload_b64)
    return base64.urlsafe_b64encode(
        payload_b64 + b"." + base64.urlsafe_b64encode(signature)
    ).decode("ascii")


def decode_cursor(secret: str, cursor: str) -> GraphCursorState:
    try:
        outer = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload_b64, sig_b64 = outer.split(b".", 1)
        signature = base64.urlsafe_b64decode(sig_b64)
    except Exception as exc:  # noqa: BLE001 - any malformed input is InvalidCursorError
        raise InvalidCursorError("Malformed cursor") from exc

    expected = _sign(secret, payload_b64)
    if not hmac.compare_digest(expected, signature):
        raise InvalidCursorError("Cursor signature mismatch")

    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        raise InvalidCursorError("Malformed cursor payload") from exc

    return GraphCursorState(
        seeds=tuple(payload["seeds"]),
        direction=payload["direction"],
        max_depth=payload["max_depth"],
        max_nodes_per_level=payload["max_nodes_per_level"],
        max_total_nodes=payload["max_total_nodes"],
        frontier=tuple(payload["frontier"]),
        visited=tuple(payload["visited"]),
        depth_reached=payload["depth_reached"],
        total_nodes_emitted=payload["total_nodes_emitted"],
        dedup_enabled=payload.get("dedup_enabled", False),
        extra=payload.get("extra", {}),
    )
