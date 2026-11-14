import asyncio
from types import SimpleNamespace

import pytest

from core.errors import RunTimeoutError
from core.limits import RunLimiter
from core.runner import stream_run


async def test_stream_deadline_is_total_and_closes_graph(monkeypatch):
    closed = False

    class Graph:
        async def astream(self, *args, **kwargs):
            nonlocal closed
            try:
                for i in range(10):
                    await asyncio.sleep(0.02)
                    yield {"node": {"data": i}}
            finally:
                closed = True

    limiter = RunLimiter(concurrency=1, timeout_seconds=0.07)
    monkeypatch.setattr("core.runner.registry.get_thread", lambda _: SimpleNamespace(graph_id="g"))
    monkeypatch.setattr("core.runner.registry.get_graph", lambda _: SimpleNamespace(definition={}))
    monkeypatch.setattr("core.runner.get_manager", lambda: SimpleNamespace(get=lambda: None))
    monkeypatch.setattr("core.runner.compile_graph", lambda *args, **kwargs: Graph())
    monkeypatch.setattr("core.runner.get_limiter", lambda: limiter)
    events = []
    with pytest.raises(RunTimeoutError):
        async for event in stream_run("thread", {}):
            events.append(event)
    assert 1 <= len(events) < 10
    assert closed
    async with limiter.acquire():
        pass


async def test_slow_consumer_cannot_hold_run_past_deadline(monkeypatch):
    closed = asyncio.Event()

    class Graph:
        async def astream(self, *args, **kwargs):
            try:
                for i in range(100):
                    yield {"node": {"data": i}}
            finally:
                closed.set()

    limiter = RunLimiter(concurrency=1, timeout_seconds=0.05)
    monkeypatch.setattr("core.runner.registry.get_thread", lambda _: SimpleNamespace(graph_id="g"))
    monkeypatch.setattr("core.runner.registry.get_graph", lambda _: SimpleNamespace(definition={}))
    monkeypatch.setattr("core.runner.get_manager", lambda: SimpleNamespace(get=lambda: None))
    monkeypatch.setattr("core.runner.compile_graph", lambda *args, **kwargs: Graph())
    monkeypatch.setattr("core.runner.get_limiter", lambda: limiter)
    stream = stream_run("thread", {})
    assert await anext(stream) == {"node": 0}
    await asyncio.wait_for(closed.wait(), timeout=1)
    async with limiter.acquire():
        pass
    with pytest.raises(RunTimeoutError):
        await anext(stream)
