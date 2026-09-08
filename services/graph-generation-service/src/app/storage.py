from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from app.domain import GeneratedGraph
from app.schemas import GraphResource, LabelMode
from graph_safety.limits import LIMITS, ResourceLimitError, check_result


@dataclass(frozen=True, slots=True)
class StoredGraph:
    resource: GraphResource
    generated: GeneratedGraph
    labels: LabelMode


class GraphStore:
    """Atomic FIFO admission with a conservative retained-memory estimate."""

    def __init__(self) -> None:
        self._entries: OrderedDict[str, tuple[StoredGraph, int]] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    def put(self, key: str, value: StoredGraph, *, capacity: int, edge_capacity: int = 5_000_000) -> None:
        check_result(value.generated.num_nodes, value.generated.num_edges)
        if capacity < 1 or value.generated.num_edges > edge_capacity:
            raise ResourceLimitError("graph exceeds the storage capacity")
        weight = (
            4096
            + value.generated.num_nodes * 1024
            + value.generated.num_edges * 2048
            + len(json.dumps(value.resource.model_dump()).encode()) * 8
        )
        if weight > LIMITS.stored_bytes:
            raise ResourceLimitError("graph exceeds the retained-memory budget")
        with self._lock:
            if key in self._entries:
                self._bytes -= self._entries.pop(key)[1]
            while self._entries and (
                len(self._entries) >= capacity
                or self._bytes + weight > LIMITS.stored_bytes
                or sum(entry[0].generated.num_edges for entry in self._entries.values()) + value.generated.num_edges
                > edge_capacity
            ):
                self._bytes -= self._entries.popitem(last=False)[1][1]
            self._entries[key] = (value, weight)
            self._bytes += weight

    def get(self, key: str) -> StoredGraph | None:
        with self._lock:
            entry = self._entries.get(key)
            return entry[0] if entry else None

    def delete(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.pop(key, None)
            if entry is None:
                return False
            self._bytes -= entry[1]
            return True

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
