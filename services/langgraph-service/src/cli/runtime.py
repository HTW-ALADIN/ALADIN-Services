import os
from contextlib import asynccontextmanager
from pathlib import Path

from config import settings
from core.checkpointer import CheckpointerManager, reset_manager, set_manager
from core.limits import RunLimiter, reset_limiter, set_limiter
from core.store import registry


@asynccontextmanager
async def runtime():
    postgres = settings.checkpointer == "postgres"
    if postgres:
        manager = CheckpointerManager(mode="postgres", postgres_url=settings.postgres_url)
    else:
        state_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        state_dir = state_dir / "langgraph-service"
        manager = CheckpointerManager(
            mode="sqlite", sqlite_path=str(state_dir / "checkpoints.sqlite3")
        )
    try:
        if not postgres:
            registry.configure(str(state_dir / "registry.sqlite3"))
        await manager.initialize()
        if postgres:
            registry.configure(settings.postgres_url, postgres=True)
        set_manager(manager)
        set_limiter(
            RunLimiter(
                concurrency=settings.run_concurrency, timeout_seconds=settings.run_timeout_seconds
            )
        )
        yield
    finally:
        reset_manager()
        reset_limiter()
        registry.configure()
        await manager.aclose()
