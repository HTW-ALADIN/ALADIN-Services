"""Admission control: per-run timeouts and process-wide run concurrency."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from core.errors import RunBusyError, RunTimeoutError


class RunLimiter:
    """Semaphore-guarded run admission with wall-deadline enforcement."""

    def __init__(self, *, concurrency: int, timeout_seconds: float) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._timeout_seconds = timeout_seconds

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        # Fast-fail without queueing: mirrors graph-generation-service
        # admission control (503 instead of unbounded wait). Gate on the
        # counter directly and re-check after acquiring: two coroutines can
        # both observe a free slot before either acquires.
        if self._semaphore._value <= 0:  # noqa: SLF001
            raise RunBusyError("server is at run capacity; retry later")
        await self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()

    async def run_with_timeout(self, coro):
        started = time.monotonic()
        try:
            return await asyncio.wait_for(coro, timeout=self._timeout_seconds)
        except TimeoutError as exc:
            elapsed = time.monotonic() - started
            raise RunTimeoutError(
                f"run exceeded {self._timeout_seconds}s deadline ({elapsed:.1f}s)"
            ) from exc


_limiter: RunLimiter | None = None


def get_limiter() -> RunLimiter:
    if _limiter is None:
        raise RuntimeError("run limiter is not initialized")
    return _limiter


def set_limiter(limiter: RunLimiter) -> None:
    global _limiter
    _limiter = limiter


def reset_limiter() -> None:
    global _limiter
    _limiter = None
