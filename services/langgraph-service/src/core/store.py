"""In-memory registries for graph definitions and thread metadata.

Ephemeral by design in v1: re-POST graph definitions after a restart.
Thread checkpoint payloads live in the LangGraph checkpointer, not here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from core.dsl import GraphDefinition


@dataclass
class StoredGraph:
    graph_id: str
    definition: GraphDefinition
    created_at: str


@dataclass
class StoredThread:
    thread_id: str
    graph_id: str
    created_at: str
    metadata: dict = field(default_factory=dict)


class Registry:
    """Thread-safe in-memory store for graphs and threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._graphs: dict[str, StoredGraph] = {}
        self._threads: dict[str, StoredThread] = {}

    def create_graph(self, definition: GraphDefinition) -> StoredGraph:
        graph_id = f"gr_{uuid4().hex[:16]}"
        stored = StoredGraph(
            graph_id=graph_id,
            definition=definition,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        with self._lock:
            self._graphs[graph_id] = stored
        return stored

    def get_graph(self, graph_id: str) -> StoredGraph | None:
        with self._lock:
            return self._graphs.get(graph_id)

    def list_graphs(self) -> list[StoredGraph]:
        with self._lock:
            return list(self._graphs.values())

    def delete_graph(self, graph_id: str) -> bool:
        with self._lock:
            return self._graphs.pop(graph_id, None) is not None

    def create_thread(self, graph_id: str) -> StoredThread:
        thread_id = f"th_{uuid4().hex[:16]}"
        stored = StoredThread(
            thread_id=thread_id,
            graph_id=graph_id,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        with self._lock:
            self._threads[thread_id] = stored
        return stored

    def get_thread(self, thread_id: str) -> StoredThread | None:
        with self._lock:
            return self._threads.get(thread_id)

    def delete_thread(self, thread_id: str) -> bool:
        with self._lock:
            return self._threads.pop(thread_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._graphs.clear()
            self._threads.clear()


registry = Registry()
