"""Lazy-loading, TTL-evicting cache for the gensim ConceptNet Numberbatch model.

The explicit problem this solves is "high idle RAM when running locally": the
~1.2 GB / ~3-6 GB KeyedVectors must not sit resident in a process nobody has asked
to use yet. So the model is loaded only on first access and dropped from RAM after
an inactivity TTL (see the ADR: docs/adr/0001-conceptnet-as-sidecar.md).
"""

import asyncio
import gc
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Path to the Numberbatch model artifact. REQUIRED — but only validated at the
# first load attempt, never at import/start, so a missing model can't block the
# /health liveness/readiness checks out of the box.
MODEL_PATH = os.environ.get("CONCEPTNET_MODEL_PATH", "")

# Seconds of inactivity before the loaded model is evicted from RAM.
IDLE_TTL_SECONDS = int(os.environ.get("CONCEPTNET_IDLE_TTL_SECONDS", "900"))

# How often the background task checks whether the model has gone idle.
EVICTION_CHECK_INTERVAL_SECONDS = int(os.environ.get("CONCEPTNET_EVICTION_CHECK_INTERVAL_SECONDS", "60"))

# Load the model synchronously at app start instead of lazily on first use.
# True for deploys that prefer to pay RAM upfront so the first request is never
# delayed by a cold load (an explicit trade-off: you pay ~3-6 GB permanently).
PRELOAD_ON_START = os.environ.get("CONCEPTNET_PRELOAD_ON_START", "false").lower() in ("1", "true", "yes")

_NUMERBATCH_KEYS = ("conceptnet-numberbatch-17-06-300",)


class ModelFileError(RuntimeError):
    """The configured model path is missing or could not be loaded.

    Deliberately raised only from an actual load attempt (never at import/start),
    so it surfaces as a 503 from the readiness/relatedness endpoints rather than
    preventing the liveness check from passing.
    """


class ModelCache:
    """Thread- and asyncio-safe singleton handle on the (optional) loaded model."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._loaded_at: float | None = None
        self._last_used: float | None = None
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    def get_model(self) -> Any:
        """Return the loaded KeyedVectors, loading it lazily if not resident."""
        with self._lock:
            if self._model is None:
                self._model = self._load()
                self._loaded_at = time.time()
            self._last_used = time.time()
            return self._model

    def evict_if_idle(self) -> bool:
        """Drop the model if it has been unused past the TTL. Returns True if evicted."""
        with self._lock:
            if self._model is None:
                return False
            if self._last_used is not None and time.time() - self._last_used >= IDLE_TTL_SECONDS:
                logger.info("evicting idle ConceptNet model after %.0fs without use", IDLE_TTL_SECONDS)
                self._model = None
                self._loaded_at = None
                self._last_used = None
                gc.collect()
                return True
            return False

    def status(self) -> dict[str, Any]:
        """Snapshot for the /v1/status endpoint."""
        now = time.time()
        idle = int(now - self._last_used) if self._last_used is not None else None
        return {
            "model_loaded": self._model is not None,
            "loaded_at": int(self._loaded_at) if self._loaded_at else None,
            "idle_seconds": idle,
            "ttl_seconds": IDLE_TTL_SECONDS,
        }

    # ── Internals ───────────────────────────────────────────────────────────

    def _load(self) -> Any:
        if not MODEL_PATH:
            raise ModelFileError("CONCEPTNET_MODEL_PATH is not set; point it at the Numberbatch KeyedVectors file.")

        from gensim.models import KeyedVectors

        path = os.fspath(MODEL_PATH)
        if not os.path.exists(path):
            raise ModelFileError(f"Model file not found at CONCEPTNET_MODEL_PATH: {MODEL_PATH}")

        start = time.monotonic()
        try:
            # Numberbatch is distributed as a native gensim KeyedVectors file
            # (`.kv`/`.vec`). Prefer a direct load; fall back to word2vec-format
            # parsing for the plain-text distribution.
            try:
                model = KeyedVectors.load(path)
            except Exception:  # noqa: BLE001 - try the word2vec text format next
                model = KeyedVectors.load_word2vec_format(path, binary=False)
        except Exception as e:  # noqa: BLE001
            raise ModelFileError(f"Failed to load ConceptNet model from {MODEL_PATH}: {e}") from None
        logger.info("loaded ConceptNet Numberbatch model in %.1fs", time.monotonic() - start)
        return model


def _load_sync() -> Any:
    """Load the model synchronously if ``CONCEPTNET_PRELOAD_ON_START=true``."""
    if not PRELOAD_ON_START:
        return None
    try:
        cache.get_model()
    except ModelFileError:
        logger.warning("CONCEPTNET_PRELOAD_ON_START=true but model could not be loaded: %s", MODEL_PATH)
        return None
    return None


cache = ModelCache()


async def eviction_loop() -> None:
    """Background task: periodically evict the model once it goes idle."""
    while True:
        await asyncio.sleep(EVICTION_CHECK_INTERVAL_SECONDS)
        cache.evict_if_idle()
