"""Unit tests for the checkpointer factory and run limiter."""

import pytest

from core.checkpointer import CheckpointerManager
from core.errors import CheckpointerNotReadyError, RunBusyError, RunTimeoutError
from core.limits import RunLimiter


async def test_memory_checkpointer_initializes():
    manager = CheckpointerManager(mode="memory")
    await manager.initialize()
    assert manager.ready is True
    assert manager.get() is not None
    ok, _ = await manager.health()
    assert ok is True


async def test_postgres_mode_requires_url():
    with pytest.raises(CheckpointerNotReadyError, match="POSTGRES_URL"):
        CheckpointerManager(mode="postgres", postgres_url="")


def test_unknown_mode_rejected():
    with pytest.raises(CheckpointerNotReadyError, match="unknown"):
        CheckpointerManager(mode="redis")


async def test_limiter_rejects_when_full():
    limiter = RunLimiter(concurrency=1, timeout_seconds=5.0)
    async with limiter.acquire():
        with pytest.raises(RunBusyError):
            async with limiter.acquire():
                pass  # pragma: no cover


async def test_limiter_enforces_timeout():
    import asyncio

    limiter = RunLimiter(concurrency=1, timeout_seconds=0.01)
    with pytest.raises(RunTimeoutError):
        await limiter.run_with_timeout(asyncio.sleep(1))
