"""Domain errors shared by the graph engine.

Routes map these to HTTP status codes; the CLI maps them to exit codes.
"""

from __future__ import annotations

from typing import Any


class DSLValidationError(ValueError):
    """A caller-supplied graph definition is invalid (maps to HTTP 400)."""


class NodeExecutionError(Exception):
    """A graph node failed at runtime (maps to HTTP 502)."""

    def __init__(self, node_id: str, message: str, upstream_status: int | None = None) -> None:
        self.node_id = node_id
        self.upstream_status = upstream_status
        super().__init__(f"node {node_id!r} failed: {message}")

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"node_id": self.node_id, "message": str(self)}
        if self.upstream_status is not None:
            payload["upstream_status"] = self.upstream_status
        return payload


class RunBusyError(Exception):
    """All run slots are in use (maps to HTTP 503)."""


class RunTimeoutError(Exception):
    """A run exceeded its wall deadline (maps to HTTP 504)."""


class CheckpointerNotReadyError(Exception):
    """The configured checkpointer cannot serve requests (maps to HTTP 503)."""
