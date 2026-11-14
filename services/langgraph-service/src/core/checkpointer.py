"""Checkpointer factory for the service and CLI."""

from __future__ import annotations

from typing import Any

from core.errors import CheckpointerNotReadyError


class CheckpointerManager:
    """Owns the LangGraph checkpointer lifecycle for one process."""

    def __init__(self, *, mode: str, postgres_url: str = "", sqlite_path: str = "") -> None:
        if mode not in ("memory", "postgres", "sqlite"):
            raise CheckpointerNotReadyError(f"unknown checkpointer mode {mode!r}")
        if mode == "postgres" and not postgres_url.strip():
            raise CheckpointerNotReadyError(
                "POSTGRES_URL is required for postgres checkpointer mode"
            )
        if mode == "sqlite" and not sqlite_path:
            raise CheckpointerNotReadyError("SQLite path is required for sqlite checkpointer mode")
        self._mode = mode
        self._postgres_url = postgres_url
        self._sqlite_path = sqlite_path
        self._checkpointer: Any | None = None
        self._saver_context: Any | None = None
        self._ready = False
        self._detail = "not initialized"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def detail(self) -> str:
        return self._detail

    async def initialize(self) -> None:
        if self._mode == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            self._checkpointer = InMemorySaver()
            self._ready = True
            self._detail = "in-memory checkpointer ready"
            return
        if self._mode == "postgres":
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            saver_context = AsyncPostgresSaver.from_conn_string(self._postgres_url)
        else:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            saver_context = AsyncSqliteSaver.from_conn_string(self._sqlite_path)

        try:
            saver = await saver_context.__aenter__()
            self._saver_context = saver_context
            await saver.setup()
        except BaseException as exc:
            self._ready = False
            self._detail = f"{self._mode} checkpointer initialization failed"
            closer = getattr(self._saver_context, "__aexit__", None)
            if closer is not None:
                try:
                    await closer(type(exc), exc, exc.__traceback__)
                except Exception:
                    pass
            self._saver_context = None
            if not isinstance(exc, Exception):
                raise
            raise CheckpointerNotReadyError(self._detail) from exc
        self._checkpointer = saver
        self._ready = True
        self._detail = f"{self._mode} checkpointer ready"

    def get(self) -> Any:
        if not self._ready or self._checkpointer is None:
            raise CheckpointerNotReadyError(f"checkpointer not ready: {self._detail}")
        return self._checkpointer

    async def health(self) -> tuple[bool, str]:
        if self._mode == "memory":
            return self._ready, "memory checkpointer ready" if self._ready else self._detail
        if not self._ready or self._checkpointer is None:
            return False, self._detail
        return True, f"{self._mode} checkpointer ready"

    async def aclose(self) -> None:
        context, self._saver_context = self._saver_context, None
        if context is not None:
            try:
                await context.__aexit__(None, None, None)
            except Exception:
                pass
        self._checkpointer = None
        self._ready = False


_manager: CheckpointerManager | None = None


def get_manager() -> CheckpointerManager:
    if _manager is None:
        raise CheckpointerNotReadyError("checkpointer manager is not initialized")
    return _manager


def set_manager(manager: CheckpointerManager) -> None:
    global _manager
    _manager = manager


def reset_manager() -> None:
    global _manager
    _manager = None
