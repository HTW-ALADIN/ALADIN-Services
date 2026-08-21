"""HTTP proxy to the text-similarity-dkpro-service (Java sidecar).

Routes requests with backend "dkpro" (topic_model, structural_stylistic, and
the optional dkpro backend extensions) to the sidecar's HTTP endpoint.

The sidecar's base URL is configurable via the TEXT_SIMILARITY_DKPRO_URL
environment variable (defaults to http://localhost:8100).
"""

import os
import threading
import time
from typing import Any

import httpx

SIDECAR_BASE_URL = os.environ.get("TEXT_SIMILARITY_DKPRO_URL", "http://localhost:8100")

# Measures implemented only by the DKPro sidecar
DKPRO_MEASURES = {"topic_model", "structural_stylistic"}

# Optional dkpro backend extensions — routed only when backend == "dkpro"
DKPRO_BACKEND_EXTENSIONS = {
    "tfidf_cosine",
    "wordnet_similarity",
}

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)

_REACH_LOCK = threading.Lock()
_REACH_TS = 0.0
_REACH_CACHE = False
_REACH_CACHE_SECONDS = 5.0


def is_dkpro_reachable() -> bool:
    """Best-effort live check that the DKPro sidecar is up (cached briefly).

    Unlike the ConceptNet sidecar there is no ``/health/ready``; probe the
    sidecar's own health endpoint. Used by the discovery endpoint; never raises.
    """
    global _REACH_TS, _REACH_CACHE
    with _REACH_LOCK:
        now = time.monotonic()
        if now - _REACH_TS < _REACH_CACHE_SECONDS:
            return _REACH_CACHE
    try:
        with httpx.Client(timeout=httpx.Timeout(1.0, connect=1.0)) as client:
            ok = client.get(f"{SIDECAR_BASE_URL}/v1/dkpro/health").status_code == 200
    except httpx.HTTPError:
        ok = False
    with _REACH_LOCK:
        _REACH_TS = time.monotonic()
        _REACH_CACHE = ok
    return ok


def is_dkpro_request(measure: str, backend: str | None) -> bool:
    """Determine whether a request should be forwarded to the DKPro sidecar."""
    if measure in DKPRO_MEASURES:
        return True
    if backend == "dkpro" and measure in DKPRO_BACKEND_EXTENSIONS:
        return True
    return False


def compute_via_sidecar(measure: str, variant: str | None, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Forward a computation to the DKPro sidecar and return its result.

    Raises:
        httpx.HTTPError: if the sidecar is unreachable or returns an error.
    """
    text_a = input_data.get("text_a", "")
    text_b = input_data.get("text_b", "")

    payload = {
        "measure": measure,
        "variant": variant,
        "textA": text_a,
        "textB": text_b,
        "params": params,
    }

    start = time.monotonic()
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{SIDECAR_BASE_URL}/v1/dkpro/similarity", json=payload)
    elapsed = time.monotonic() - start

    if resp.status_code >= 400:
        # Try to extract the sidecar's error message
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        raise httpx.HTTPStatusError(
            f"DKPro sidecar returned HTTP {resp.status_code}: {detail}",
            request=resp.request,
            response=resp,
        )

    data = resp.json()
    result = {
        "raw": data.get("similarity"),
        "similarity": data.get("similarity"),
        "distance": data.get("distance"),
        "compute_time_ms": data.get("computeTimeMs", round(elapsed * 1000, 2)),
    }
    return result
