from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
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
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._graphs: dict[str, StoredGraph] = {}
        self._threads: dict[str, StoredThread] = {}
        self._database: str | None = None
        self._postgres = False

    def configure(self, database: str | None = None, *, postgres: bool = False) -> None:
        with self._lock:
            self._database = database
            self._postgres = postgres
            if database:
                if not postgres:
                    Path(database).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with closing(self._connect()) as conn, conn:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS lg_graphs (graph_id TEXT PRIMARY KEY, "
                        "definition TEXT NOT NULL, created_at TEXT NOT NULL)"
                    )
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS lg_threads (thread_id TEXT PRIMARY KEY, "
                        "graph_id TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL)"
                    )

    def _connect(self):
        if self._postgres:
            import psycopg

            return psycopg.connect(self._database)
        return sqlite3.connect(self._database)

    def _execute(self, sql: str, params: tuple = (), *, fetch: bool = False):
        with self._lock, closing(self._connect()) as conn, conn:
            cursor = conn.execute(sql.replace("?", "%s") if self._postgres else sql, params)
            return cursor.fetchall() if fetch else cursor.rowcount

    def create_graph(self, definition: GraphDefinition) -> StoredGraph:
        stored = StoredGraph(
            f"gr_{uuid4().hex[:16]}",
            definition,
            datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        if self._database:
            self._execute(
                "INSERT INTO lg_graphs VALUES (?, ?, ?)",
                (stored.graph_id, definition.model_dump_json(), stored.created_at),
            )
        else:
            with self._lock:
                self._graphs[stored.graph_id] = stored
        return stored

    def get_graph(self, graph_id: str) -> StoredGraph | None:
        if self._database:
            rows = self._execute(
                "SELECT graph_id, definition, created_at FROM lg_graphs WHERE graph_id = ?",
                (graph_id,),
                fetch=True,
            )
            return (
                StoredGraph(rows[0][0], GraphDefinition.model_validate_json(rows[0][1]), rows[0][2])
                if rows
                else None
            )
        with self._lock:
            return self._graphs.get(graph_id)

    def list_graphs(self) -> list[StoredGraph]:
        if self._database:
            rows = self._execute(
                "SELECT graph_id, definition, created_at FROM lg_graphs "
                "ORDER BY created_at, graph_id",
                fetch=True,
            )
            return [
                StoredGraph(row[0], GraphDefinition.model_validate_json(row[1]), row[2])
                for row in rows
            ]
        with self._lock:
            return list(self._graphs.values())

    def delete_graph(self, graph_id: str) -> bool:
        if self._database:
            return bool(self._execute("DELETE FROM lg_graphs WHERE graph_id = ?", (graph_id,)))
        with self._lock:
            return self._graphs.pop(graph_id, None) is not None

    def create_thread(self, graph_id: str) -> StoredThread:
        stored = StoredThread(
            f"th_{uuid4().hex[:16]}", graph_id, datetime.now(UTC).isoformat().replace("+00:00", "Z")
        )
        if self._database:
            self._execute(
                "INSERT INTO lg_threads VALUES (?, ?, ?, ?)",
                (stored.thread_id, graph_id, stored.created_at, json.dumps(stored.metadata)),
            )
        else:
            with self._lock:
                self._threads[stored.thread_id] = stored
        return stored

    def get_thread(self, thread_id: str) -> StoredThread | None:
        if self._database:
            rows = self._execute(
                "SELECT thread_id, graph_id, created_at, metadata FROM lg_threads "
                "WHERE thread_id = ?",
                (thread_id,),
                fetch=True,
            )
            return (
                StoredThread(rows[0][0], rows[0][1], rows[0][2], json.loads(rows[0][3]))
                if rows
                else None
            )
        with self._lock:
            return self._threads.get(thread_id)

    def delete_thread(self, thread_id: str) -> bool:
        if self._database:
            return bool(self._execute("DELETE FROM lg_threads WHERE thread_id = ?", (thread_id,)))
        with self._lock:
            return self._threads.pop(thread_id, None) is not None

    def clear(self) -> None:
        if self._database:
            self._execute("DELETE FROM lg_threads")
            self._execute("DELETE FROM lg_graphs")
        else:
            with self._lock:
                self._graphs.clear()
                self._threads.clear()


registry = Registry()
