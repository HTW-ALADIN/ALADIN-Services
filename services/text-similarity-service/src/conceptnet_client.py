"""HTTP proxy to the conceptnet-sidecar service (local ConceptNet Numberbatch).

Routes ``embedding_cosine`` variant ``conceptnet_numberbatch`` with
``params.backend: local`` (the default) to the standalone sidecar's HTTP endpoint,
so the main service never loads the ~3-6 GB gensim model in-process.

The sidecar's base URL is configurable via the TEXT_SIMILARITY_CONCEPTNET_URL
environment variable (defaults to http://localhost:8200). It works with either
main image (cpu/hf).
"""

import os
import threading
import time
from typing import Any

import httpx

SIDECAR_BASE_URL = os.environ.get("TEXT_SIMILARITY_CONCEPTNET_URL", "http://localhost:8200")

# 5s timeout, mirroring the remote ConceptNet API client (conceptnet_api.py).
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# A single shared client reused across calls: reusing the connection pool avoids
# a fresh TCP/TLS handshake per input pair, which matters for batched requests.
_shared_client = httpx.Client(timeout=_TIMEOUT)


_reach_lock = threading.Lock()
_reach_ts = 0.0
_reach_cache = False
_REACH_CACHE_SECONDS = 5.0


class ConceptNetSidecarError(Exception):
    """Raised when the ConceptNet sidecar call fails; maps to problem+json.

    ``status`` is 503 for unreachable/connection issues (the sidecar is optional,
    so its absence is a soft degradation, not a hard 500) and 502 for other
    upstream/response errors.
    """

    def __init__(self, message: str, *, status: int = 503) -> None:
        super().__init__(message)
        self.status = status


def is_sidecar_reachable() -> bool:
    """Best-effort live check that the ConceptNet sidecar is up and ready.

    Used by the discovery endpoint (best effort, short timeout, cached for a few
    seconds so frequent discovery polls don't block on the sidecar). Never
    raises; returns False on any failure so discovery degrades gracefully.
    """
    global _reach_ts, _reach_cache
    with _reach_lock:
        now = time.monotonic()
        if now - _reach_ts < _REACH_CACHE_SECONDS:
            return _reach_cache
    try:
        # Use a tiny per-call client so a probe can never hang a shared pool.
        with httpx.Client(timeout=httpx.Timeout(1.0, connect=1.0)) as client:
            ok = client.get(f"{SIDECAR_BASE_URL}/health/ready").status_code == 200
    except httpx.HTTPError:
        ok = False
    with _reach_lock:
        _reach_ts = time.monotonic()
        _reach_cache = ok
    return ok


def get_relatedness(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score a batch of word pairs via the ConceptNet sidecar.

    Example pair: ``{"id", "word_a", "word_b", "lang"}``. Returns one item per
    pair: ``{"id", "score", "error"}`` (score is None + error set for OOV words).

    Raises:
        ConceptNetSidecarError: sidecar unreachable/timed out (status 503) or
            returned an error (status 502). Never raises a raw httpx error, so
            callers can map the exception's ``status`` to problem+json directly.
    """
    try:
        start = time.monotonic()
        resp = _shared_client.post(f"{SIDECAR_BASE_URL}/v1/relatedness", json={"pairs": pairs})
        elapsed = time.monotonic() - start
    except httpx.TimeoutException as e:
        raise ConceptNetSidecarError(f"ConceptNet sidecar timed out: {e}", status=503) from None
    except httpx.HTTPError as e:
        raise ConceptNetSidecarError(f"ConceptNet sidecar unreachable: {e}", status=503) from None

    if resp.status_code >= 400:
        raise ConceptNetSidecarError(
            f"ConceptNet sidecar returned HTTP {resp.status_code}",
            status=502,
        )

    items = resp.json()
    if isinstance(items, list):
        for item in items:
            if "compute_time_ms" not in item:
                item["compute_time_ms"] = round(elapsed * 1000, 2)
    return items
