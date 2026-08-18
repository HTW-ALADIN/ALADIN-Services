"""HTTP client for the public ConceptNet relatedness API (remote backend).

Used by ``embedding_cosine`` variant ``conceptnet_numberbatch`` when
``params.backend == "remote"`` (the default): the API hosts a reduced ConceptNet
Numberbatch matrix server-side, so the local ~1.2 GB gensim download is avoided.

External API (NOT under our control): ``GET https://api.conceptnet.io/
relatedness?node1=/c/{lang}/{a}&node2=/c/{lang}/{b}`` — 3600 requests/hour
sustained, 120/minute burst, no API key. There is NO comparable public API for
``glove`` / ``fasttext`` (they stay local gensim downloads).

Failure policy: never silently fall back to the local gensim model (that would
trigger the 1.2 GB download). Network errors / timeouts / HTTP 429 (after
client-side backoff) map to 503 problem+json; other upstream errors to 502.
``main.py`` translates :class:`ConceptNetError` into problem+json.
"""

import os
import random
import re
import threading
import time

import httpx

CONCEPTNET_BASE_URL = os.environ.get("CONCEPTNET_API_URL", "https://api.conceptnet.io")
REMOTE_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
# Cap on inputs per batch when backend="remote": a batch of <= MAX_REMOTE_INPUTS
# stays within the API's 120/min burst. Larger batches are rejected up-front.
MAX_REMOTE_INPUTS = int(os.environ.get("CONCEPTNET_MAX_REMOTE_INPUTS", "60"))
# Min spacing between remote calls so one batch can't burn the 3600/h limit.
REMOTE_REQUEST_DELAY = float(os.environ.get("CONCEPTNET_REMOTE_REQUEST_DELAY", "0.05"))
_MAX_429_RETRIES = int(os.environ.get("CONCEPTNET_429_RETRIES", "3"))
_BACKOFF_BASE_SECONDS = 1.0
DEFAULT_LANG = "en"


class ConceptNetError(Exception):
    """Raised when the ConceptNet API fails; ``status`` (502/503) drives problem+json."""

    def __init__(self, message: str, *, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


_throttle_lock = threading.Lock()
_last_request_ts = 0.0


def _throttle() -> None:
    """Enforce a minimum spacing between consecutive remote requests.

    The lock is held only long enough to atomically claim the next permitted
    send slot; the actual ``time.sleep`` happens *outside* the lock. This keeps
    the rate limit while letting unrelated concurrent work proceed instead of
    blocking behind a thread that is sleeping.
    """
    global _last_request_ts
    wait = 0.0
    with _throttle_lock:
        now = time.monotonic()
        next_allowed = _last_request_ts + REMOTE_REQUEST_DELAY
        if next_allowed > now:
            wait = next_allowed - now
            _last_request_ts = next_allowed  # claim this slot atomically
        else:
            _last_request_ts = now
    if wait > 0:
        time.sleep(wait)


def _to_conceptnet_uri(word: str, lang: str = DEFAULT_LANG) -> str:
    """Normalize a word to a ConceptNet ``/c/{lang}/{term}`` URI (spaces -> underscores)."""
    term = re.sub(r"[^0-9A-Za-z_]+", "_", "_".join(word.split())).strip("_")
    return f"/c/{lang}/{term}"


def compute_relatedness_remote(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Compute ConceptNet relatedness for one pair; maps the API's ``value`` to the result schema."""
    a = input_data.get("text_a", "")
    b = input_data.get("text_b", "")
    lang = str(params.get("lang", DEFAULT_LANG))
    uri_a = _to_conceptnet_uri(a, lang)
    uri_b = _to_conceptnet_uri(b, lang)
    term_a = uri_a.rsplit("/", 1)[-1]
    term_b = uri_b.rsplit("/", 1)[-1]

    if not term_a and not term_b:
        raw = 1.0  # both sides empty/meaningless -> identical
    elif not term_a or not term_b:
        raw = 0.0  # exactly one empty side -> nothing in common
    else:
        raw = _fetch_relatedness(uri_a, uri_b)

    return {"raw": raw, "similarity": raw, "distance": 1.0 - raw, "source": "conceptnet_api"}


def _fetch_relatedness(uri_a: str, uri_b: str) -> float:
    """GET relatedness with throttle, timeout and 429 backoff; returns a float or raises."""
    query = {"node1": uri_a, "node2": uri_b}
    for attempt in range(_MAX_429_RETRIES + 1):
        _throttle()
        try:
            with httpx.Client(timeout=REMOTE_TIMEOUT) as client:
                resp = client.get(f"{CONCEPTNET_BASE_URL}/relatedness", params=query)
        except httpx.TimeoutException as e:
            raise ConceptNetError(f"ConceptNet API timed out ({REMOTE_TIMEOUT}) for {uri_a} vs {uri_b}: {e}", status=503) from None
        except httpx.HTTPError as e:
            raise ConceptNetError(f"ConceptNet API unreachable for {uri_a} vs {uri_b}: {e}", status=503) from None

        if resp.status_code == 429:
            if attempt < _MAX_429_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.5))
                continue
            raise ConceptNetError(f"ConceptNet API rate limit exceeded (HTTP 429 after {_MAX_429_RETRIES} retries)", status=503)
        if resp.status_code >= 400:
            raise ConceptNetError(f"ConceptNet API returned HTTP {resp.status_code}: {resp.text[:200]}", status=502)

        try:
            value = resp.json().get("value")
        except Exception as e:  # noqa: BLE001
            raise ConceptNetError(f"ConceptNet API returned non-JSON response: {e}", status=502) from None
        if not isinstance(value, (int, float)):
            raise ConceptNetError("ConceptNet API response missing numeric 'value' field", status=502)
        return float(value)
