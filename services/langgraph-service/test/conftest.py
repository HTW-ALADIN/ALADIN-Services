import asyncio

import pytest


@pytest.fixture(autouse=True)
def _reset_state(tmp_path, monkeypatch):
    from core import checkpointer, limits
    from core.store import registry

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    registry.configure()
    registry.clear()
    manager = checkpointer.CheckpointerManager(mode="memory")
    asyncio.run(manager.initialize())
    checkpointer.set_manager(manager)
    limits.set_limiter(limits.RunLimiter(concurrency=4, timeout_seconds=120))
    yield
    registry.configure()
    registry.clear()
    checkpointer.reset_manager()
    limits.reset_limiter()
