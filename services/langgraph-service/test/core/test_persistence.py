import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from core.dsl import GraphDefinition
from core.store import Registry, registry

CLI = Path(sys.executable).parent / (
    "langgraph-service.exe" if sys.platform == "win32" else "langgraph-service"
)

GRAPH = {
    "name": "persisted",
    "nodes": [{"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]}],
    "edges": [],
    "entry": "a",
}


def test_sqlite_registry_reopens(tmp_path):
    path = str(tmp_path / "registry.sqlite3")
    first = Registry()
    first.configure(path)
    graph = first.create_graph(GraphDefinition.model_validate(GRAPH))
    thread = first.create_thread(graph.graph_id)
    second = Registry()
    second.configure(path)
    assert second.get_graph(graph.graph_id) == graph
    assert second.get_thread(thread.thread_id) == thread
    assert second.delete_thread(thread.thread_id)
    assert second.delete_graph(graph.graph_id)
    assert first.get_thread(thread.thread_id) is None
    assert first.get_graph(graph.graph_id) is None


def test_cli_registry_and_checkpoints_survive_processes(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(GRAPH))
    env = {**os.environ, "XDG_STATE_HOME": str(tmp_path)}
    env.pop("PYTHONPATH", None)
    env.pop("LANGGRAPH_CHECKPOINTER", None)
    env.pop("CHECKPOINTER", None)
    env.pop("POSTGRES_URL", None)

    def invoke(*args):
        result = subprocess.run(
            [str(CLI), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return json.loads(result.stdout)

    graph_id = invoke("graph", "create", "--file", str(path))["graph_id"]
    thread_id = invoke("thread", "create", "--graph", graph_id)["thread_id"]
    assert GraphDefinition.model_validate(invoke("graph", "get", graph_id)["definition"]) == (
        GraphDefinition.model_validate(GRAPH)
    )
    first_run = invoke("run", "invoke", thread_id, "--input", '{"start": true}')
    assert first_run["output"] == {"start": True, "value": 1}
    state = invoke("thread", "state", thread_id)
    assert state["values"] == first_run["output"]
    assert len(invoke("thread", "history", thread_id)["history"]) > 0

    second_run = invoke("run", "invoke", thread_id, "--input", '{"next": true}')
    assert second_run["output"] == {"start": True, "next": True, "value": 1}
    assert invoke("thread", "state", thread_id)["values"] == second_run["output"]

    checkpoint_path = tmp_path / "langgraph-service" / "checkpoints.sqlite3"
    with sqlite3.connect(checkpoint_path) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (thread_id,)
            ).fetchone()[0]
            > 0
        )
    assert invoke("thread", "delete", thread_id)["deleted"] == thread_id
    with sqlite3.connect(checkpoint_path) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (thread_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM writes WHERE thread_id = ?", (thread_id,)
            ).fetchone()[0]
            == 0
        )
    assert invoke("graph", "delete", graph_id)["deleted"] == graph_id


@pytest.mark.parametrize("url", ["", "   "])
def test_cli_postgres_requires_url(tmp_path, url):
    env = {
        **os.environ,
        "XDG_STATE_HOME": str(tmp_path),
        "LANGGRAPH_CHECKPOINTER": "postgres",
        "POSTGRES_URL": url,
    }
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [str(CLI), "graph", "list"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "POSTGRES_URL is required" in result.stderr
    assert not (tmp_path / "langgraph-service").exists()


async def test_cli_sqlite_connection_closed_on_error():
    from cli.runtime import runtime
    from core.checkpointer import get_manager
    from core.errors import CheckpointerNotReadyError

    with pytest.raises(RuntimeError, match="command failed"):
        async with runtime():
            manager = get_manager()
            assert manager.mode == "sqlite"
            connection = manager.get().conn
            raise RuntimeError("command failed")
    assert not manager.ready
    with pytest.raises(ValueError, match="no active connection|Connection closed"):
        await connection.execute("SELECT 1")
    with pytest.raises(CheckpointerNotReadyError):
        get_manager()


async def test_cli_sqlite_connection_closed_on_setup_failure(monkeypatch):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from cli.runtime import runtime
    from core.errors import CheckpointerNotReadyError

    connection = None

    async def fail_setup(saver):
        nonlocal connection
        connection = saver.conn
        raise RuntimeError("setup failed")

    monkeypatch.setattr(AsyncSqliteSaver, "setup", fail_setup)
    with pytest.raises(
        CheckpointerNotReadyError, match="sqlite checkpointer initialization failed"
    ):
        async with runtime():
            pytest.fail("runtime should not start")
    assert connection is not None
    with pytest.raises(ValueError, match="no active connection|Connection closed"):
        await connection.execute("SELECT 1")


async def test_postgres_lifespan_requires_url(monkeypatch):
    from config import settings
    from core.errors import CheckpointerNotReadyError
    from main import app, lifespan

    monkeypatch.setattr(settings, "checkpointer", "postgres")
    monkeypatch.setattr(settings, "postgres_url", "")
    with pytest.raises(CheckpointerNotReadyError, match="POSTGRES_URL is required"):
        async with lifespan(app):
            pytest.fail("runtime should not start")


async def test_lifespan_closes_on_exception():
    from core.checkpointer import get_manager
    from core.errors import CheckpointerNotReadyError
    from main import app, lifespan

    with pytest.raises(RuntimeError, match="test failure"):
        async with lifespan(app):
            manager = get_manager()
            assert manager.ready
            raise RuntimeError("test failure")
    assert not manager.ready
    with pytest.raises(CheckpointerNotReadyError):
        get_manager()


async def test_delete_thread_removes_checkpoints():
    from api.routes.threads import delete_thread
    from core.checkpointer import get_manager

    graph = registry.create_graph(GraphDefinition.model_validate(GRAPH))
    thread = registry.create_thread(graph.graph_id)
    saver = get_manager().get()
    from langgraph.checkpoint.base import empty_checkpoint

    config = {"configurable": {"thread_id": thread.thread_id, "checkpoint_ns": ""}}
    await saver.aput(config, empty_checkpoint(), {}, {})
    assert await saver.aget_tuple(config) is not None
    assert (await delete_thread(thread.thread_id)).status_code == 204
    assert await saver.aget_tuple(config) is None
    assert registry.get_thread(thread.thread_id) is None


async def test_delete_failure_preserves_thread(monkeypatch):
    from api.routes.threads import delete_thread
    from core.checkpointer import get_manager

    graph = registry.create_graph(GraphDefinition.model_validate(GRAPH))
    thread = registry.create_thread(graph.graph_id)

    async def fail(thread_id):
        raise RuntimeError("checkpoint deletion failed")

    monkeypatch.setattr(get_manager().get(), "adelete_thread", fail)
    with pytest.raises(RuntimeError, match="checkpoint deletion failed"):
        await delete_thread(thread.thread_id)
    assert registry.get_thread(thread.thread_id) == thread


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set")
async def test_postgres_thread_survives_lifespan_restart(monkeypatch):
    from api.routes.threads import delete_thread, get_thread_state
    from config import settings
    from core.runner import invoke_run
    from main import app, lifespan

    monkeypatch.setattr(settings, "checkpointer", "postgres")
    monkeypatch.setattr(settings, "postgres_url", os.environ["TEST_POSTGRES_URL"])
    async with lifespan(app):
        graph = registry.create_graph(GraphDefinition.model_validate(GRAPH))
        thread = registry.create_thread(graph.graph_id)
        assert await invoke_run(thread.thread_id, {"start": True}) == {"start": True, "value": 1}

    async with lifespan(app):
        response = await get_thread_state(thread.thread_id)
        assert response.status_code == 200
        assert json.loads(response.body)["values"] == {"start": True, "value": 1}
        assert (await delete_thread(thread.thread_id)).status_code == 204
        assert registry.delete_graph(graph.graph_id)


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set")
def test_postgres_registry_reopens():
    url = os.environ["TEST_POSTGRES_URL"]
    first = Registry()
    first.configure(url, postgres=True)
    graph = first.create_graph(GraphDefinition.model_validate(GRAPH))
    thread = first.create_thread(graph.graph_id)
    second = Registry()
    second.configure(url, postgres=True)
    try:
        assert second.get_graph(graph.graph_id) == graph
        assert second.get_thread(thread.thread_id) == thread
    finally:
        second.delete_thread(thread.thread_id)
        second.delete_graph(graph.graph_id)
