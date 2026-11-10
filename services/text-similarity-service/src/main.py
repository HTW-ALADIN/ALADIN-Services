"""FastAPI application for the Text Similarity Service.

Mirrors the edit-distance-service API style: flat, synchronous, stateless
endpoints. Every compute request takes ``algorithm`` (+ optional ``backend``,
the default backend is auto-selected), ``params`` and a batch ``inputs`` list,
and returns the results synchronously.
"""

import logging
import os
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import conceptnet_client
from .catalog import CATALOG, PROFILE, get_catalog
from .conceptnet_api import MAX_REMOTE_INPUTS, ConceptNetError
from .conceptnet_client import ConceptNetSidecarError, is_sidecar_reachable
from .lexical import DEFAULT_LEXICAL_BACKENDS, compute_lexical
from .model_cache import LargeModelDownloadBlocked, cache_summary, is_warm, prewarm_default_gensim, warm_start
from .models import (
    LexicalRequest,
    RetrievalRequest,
    TextComputeResponse,
    TextDistanceRequest,
    TextResult,
)
from .retrieval import DEFAULT_RETRIEVAL_BACKENDS, compute_retrieval
from .similarity import (
    DEFAULT_BACKENDS,
    SIMILARITY_DISPATCH,
    _conceptnet_sidecar_result,
    compute_similarity,
    sbert_cosine_batch,
)

logger = logging.getLogger(__name__)

# Ensure the service's own log lines (errors in model computation, sidecar
# failures, ...) are actually emitted even when started standalone or by a
# bare ``uvicorn src.main:app``. ``force=False`` leaves Uvicorn's own logging
# configuration untouched when one already exists.
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Quiet the per-request chatter of the HTTP client and web framework so a
# 500-input ConceptNet batch (one request per input) doesn't drown the logs in
# "HTTP Request ..." lines. The service's own loggers stay at INFO.
for _noisy in ("httpx", "httpcore", "uvicorn.access"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


_START_TS = time.monotonic()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: optionally warm the HF model cache (``HF_PRELOAD`` != off).

    This is the main service's analogue of the ConceptNet sidecar's
    ``CONCEPTNET_PRELOAD_ON_START``. Cold by default (``HF_PRELOAD=off``) so
    boot stays fast and idle RAM tiny; when a profile (``all`` or a partial
    ``measure:model,...``) is baked in, loads the selected models once into the
    process cache so the first request for them is served instantly in exchange
    for higher idle RAM. ``warm_start`` is non-fatal — failures relax to lazy.
    """
    warm_start()
    # Start the small default gensim model (glove) downloading/loading in the
    # background so the first embedding_cosine/wmd request doesn't block on an
    # unbounded, synchronous download in the request path.
    prewarm_default_gensim()
    yield


app = FastAPI(
    title=f"Text Similarity Service ({PROFILE})",
    version="0.1.0",
    lifespan=lifespan,
    description=(
        "Unified REST API for semantic text similarity — 16 algorithm families over multiple backends. "
        f"Build variant: {PROFILE}." + ("" if PROFILE == "pytorch" else " (PyTorch-based algorithms excluded)")
    ),
)


# ─── Profile guard ────────────────────────────────────────────────────────────


def _require_enabled(algorithm: str) -> None:
    """Reject a whole algorithm that is excluded by the active profile.

    In the ``cpu`` profile (text-similarity-cpu image) the PyTorch-only
    algorithms (requires_model) are not offered. Rather than a lazy 501
    "install the extra" — that image deliberately ships without PyTorch — we
    fail fast and point the caller at the pytorch image.
    """
    if PROFILE == "pytorch":
        return
    entries = [e for e in CATALOG if e["algorithm"] == algorithm]
    if entries and all(e.get("requires_model") for e in entries):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Algorithm '{algorithm}' requires the PyTorch stack and is not available "
                f"in this build (text-similarity-cpu). Deploy the text-similarity-hf image to use it."
            ),
        )


# ─── Error Handler ────────────────────────────────────────────────────────────

# Missing optional module -> which pip extra enables it (used for the 501 body).
_MODULE_EXTRA = {"wn": "de"}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return an RFC 9457 application/problem+json body for every HTTP error."""
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": exc.detail or str(exc.status_code),
            "status": exc.status_code,
            "detail": exc.detail or "",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return request-validation errors in the same RFC 9457 problem+json shape.

    Without this, Pydantic 422s fall through to FastAPI's default handler and
    produce a structurally different body than the deliberate 400/500 errors.
    """
    # RFC 9457 wants a human-readable string in ``detail``; Pydantic returns a
    # structured list of error dicts, which is more useful for clients. Keep it
    # as the machine-readable ``errors`` field and give ``detail`` a concise string.
    errors = exc.errors()
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": "Request validation failed",
            "status": 422,
            "detail": "The request body failed schema validation",
            "errors": errors,
        },
    )


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Liveness: the process is up and serving."""
    return {"status": "ok", "service": "text-similarity-service", "profile": PROFILE}


@app.get("/health/ready")
def readiness():
    """Readiness: accepts requests now.

    The service is synchronous and stateless; it reports ready as long as the
    process is up (the app is imported), which is the effective readiness signal
    for compute. Cached-model/Memory and sidecar availability are intentionally
    NOT part of readiness, so the orchestrator never scales it away for a
    transiently warm cache. Use ``GET /metrics`` for a live cache/uptime view.
    """
    return {"status": "ready", "service": "text-similarity-service", "profile": PROFILE}


@app.get("/metrics")
def metrics():
    """Lightweight, dependency-free observability snapshot (JSON).

    For a full metrics pipeline, scrape this with Prometheus/Datadog via an
    exporter or a gateway; this endpoint is intentionally dependency-free.
    """
    import resource

    try:
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, AttributeError):  # pragma: no cover - exotic interpreters
        rss_kb = None
    return {
        "uptime_s": round(time.monotonic() - _START_TS, 2),
        "pid": os.getpid(),
        "profile": PROFILE,
        "catalog_entries": len(get_catalog()),
        "warm": is_warm(),
        "model_cache": _safe_cache_summary(),
        "peak_rss_kb": rss_kb,
    }


def _safe_cache_summary() -> dict:
    """Best-effort model-cache introspection so /metrics never raises."""
    try:
        return cache_summary()
    except Exception:  # noqa: BLE001
        logger.exception("cache_summary() failed")
        return {"keys": [], "count": -1}


# ─── Discovery ────────────────────────────────────────────────────────────────


@app.get("/v1/similarity/text/algorithms")
def list_algorithms() -> list[dict]:
    """Discovery: list all algorithm/backend combinations with metadata.

    Entries that rely on the optional ConceptNet sidecar (``requires_sidecar``)
    carry a best-effort live ``sidecar_reachable`` flag so a client can predict
    whether a request will succeed without issuing one.
    """
    catalog = get_catalog()
    conceptnet_ok = is_sidecar_reachable()
    for entry in catalog:
        if entry.get("requires_sidecar"):
            entry["sidecar_reachable"] = conceptnet_ok
    return catalog


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_backend(defaults: dict[str, str], algorithm: str, backend: str | None) -> str:
    """Auto-select the default backend when the caller omits ``backend``."""
    return backend or defaults.get(algorithm, "")


def _map_compute_error(exc: Exception, algorithm: str, backend: str, input_id: str) -> HTTPException:
    """Map any compute exception to the matching HTTP error (problem+json).

    Single source of truth for error semantics, reused by the per-item batch loop
    and the dedicated fast paths (batched SBERT): validation errors -> 400,
    ConceptNet sidecar/API failures -> 502/503, missing optional extra -> 501,
    everything else -> 500 (logged server-side, generic body so internals never
    leak into the response).
    """
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, LargeModelDownloadBlocked):
        # Cost gate: a >500 MB runtime model download was requested without an
        # explicit opt-in (params.confirm_large_download / env var). The message
        # names size, opt-in and how to enable it.
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ConceptNetSidecarError):
        # ConceptNet sidecar unavailable (optional process). Soft degradation:
        # 503 when unreachable/timed out, 502 on an upstream error — never a 500.
        return HTTPException(
            status_code=exc.status,
            detail=str(exc) + " (hint: set TEXT_SIMILARITY_CONCEPTNET_URL or start the conceptnet-sidecar service)",
        )
    if isinstance(exc, ConceptNetError):
        # External ConceptNet API failure (explicit backend: remote) -> clean
        # 502/503. No cross-backend fallback is ever performed.
        return HTTPException(status_code=exc.status, detail=f"ConceptNet API request failed: {exc}")
    if isinstance(exc, ModuleNotFoundError):
        module_name = exc.name or "unknown"
        extra = _MODULE_EXTRA.get(module_name, "model")
        return HTTPException(
            status_code=501,
            detail=(
                f"Algorithm '{algorithm}' requires the optional '{extra}' extra "
                f"(missing module '{module_name}'). Install it with: pip install -e '.[{extra}]'"
            ),
        )
    # Log the full traceback server-side (no logging existed before); the client
    # gets a generic message so internal details/stack paths never leak.
    logger.exception("Unhandled error computing %s/%s for input %s", algorithm, backend, input_id)
    return HTTPException(status_code=500, detail="Internal computation error")


def _run_batch(
    algorithm: str,
    backend: str,
    params: dict[str, Any],
    inputs: list[Any],
    make_input: Callable[[Any], dict[str, Any]],
    compute_fn: Callable[[str, str, dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> tuple[list[TextResult], float]:
    """Compute a batch of inputs, mapping each item to a TextResult.

    Errors map to problem+json via ``_map_compute_error``: validation errors ->
    400, ConceptNet sidecar failures -> 502/503, missing optional extras -> 501,
    everything else -> 500.
    """
    results: list[TextResult] = []
    total_ms = 0.0
    for item in inputs:
        input_data = make_input(item)
        try:
            res = compute_fn(algorithm, backend, input_data, params)
        except Exception as e:  # noqa: BLE001 - mapped to problem+json by the helper
            raise _map_compute_error(e, algorithm, backend, getattr(item, "id", "<unknown>")) from None
        total_ms += res.get("compute_time_ms", 0)
        results.append(TextResult(id=item.id, result=res))
    return results, round(total_ms, 2)


# ─── POST /v1/similarity/text/distance — text similarity ─────────────────────


@app.post("/v1/similarity/text/distance")
def text_distance(request: TextDistanceRequest) -> TextComputeResponse:
    """Compute similarity scores for a batch of text pairs (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    _require_enabled(algorithm)

    if (algorithm, backend) not in SIMILARITY_DISPATCH:
        supported = [b for (m, b) in SIMILARITY_DISPATCH if m == algorithm]
        raise HTTPException(
            status_code=400,
            detail=f"Backend '{backend}' not supported for algorithm '{algorithm}'. Supported: {supported}",
        )

    # The ConceptNet remote path makes one HTTP request per input against an
    # externally rate-limited public API. Reject oversized batches up-front
    # (instead of burning the 3600/h limit in seconds) with a clean 400. The
    # remote path is explicit opt-in only (local is the default for the
    # conceptnet_numberbatch variant), so the cap applies solely when
    # params.backend == "remote".
    _remote_conceptnet = (
        algorithm == "embedding_cosine"
        and backend == "gensim"
        and request.params.get("variant", "glove") == "conceptnet_numberbatch"
        and request.params.get("backend") == "remote"
    )
    if _remote_conceptnet and len(request.inputs) > MAX_REMOTE_INPUTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"embedding_cosine variant 'conceptnet_numberbatch' with params.backend='remote' supports at most "
                f"{MAX_REMOTE_INPUTS} inputs per request (got {len(request.inputs)}) to stay within the "
                f"api.conceptnet.io rate limit (3600/h, 120/min burst). Split the batch into smaller requests or "
                f"set params.backend='local'."
            ),
        )

    # Batched local ConceptNet dispatch: embed_cosine / conceptnet_numberbatch /
    # backend local (the default) is served by the conceptnet-sidecar. The whole
    # batch is scored with ONE get_relatedness call instead of one HTTP round-trip
    # per input, which matters for large batches against a cold/loaded sidecar.
    conceptnet_local = (
        algorithm == "embedding_cosine"
        and backend == "gensim"
        and request.params.get("variant", "glove") == "conceptnet_numberbatch"
        and request.params.get("backend") in (None, "local")
    )
    if conceptnet_local:
        lang = request.params.get("lang", "en")
        pairs = [{"id": item.id, "word_a": item.a, "word_b": item.b, "lang": lang} for item in request.inputs]
        try:
            sidecar_items = conceptnet_client.get_relatedness(pairs)
        except ConceptNetSidecarError as e:
            raise HTTPException(
                status_code=e.status,
                detail=str(e) + " (hint: set TEXT_SIMILARITY_CONCEPTNET_URL or start the conceptnet-sidecar service)",
            ) from None
        results: list[TextResult] = []
        total_ms = 0.0
        for item in sidecar_items:
            result = _conceptnet_sidecar_result(item, request.params)
            result["compute_time_ms"] = item.get("compute_time_ms", 0)
            total_ms += result.get("compute_time_ms", 0)
            results.append(TextResult(id=item["id"], result=result))
        return TextComputeResponse(
            algorithm=algorithm,
            backend="gensim",
            results=results,
            meta={"compute_time_ms": round(total_ms, 2)},
        )

    # Batched SBERT dispatch: encode every text in the request with ONE
    # model.encode() call (deduplicated), instead of one call per pair. This
    # mirrors the batched local-ConceptNet path and is far faster for large
    # batches, especially on GPU.
    if algorithm == "sbert_cosine" and backend == "sentence_transformers":
        pairs = [{"id": item.id, "text_a": item.a, "text_b": item.b} for item in request.inputs]
        try:
            results = sbert_cosine_batch(pairs, request.params)
        except Exception as e:  # noqa: BLE001 - mapped to problem+json by the helper
            raise _map_compute_error(e, algorithm, backend, "<batch>") from None
        total_ms = round(sum(r["result"].get("compute_time_ms", 0) for r in results), 2)
        return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})

    def _compute(alg: str, bck: str, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        # ConceptNet API failures (explicit backend: remote) surface as
        # ConceptNetError and are mapped to a clean 502/503 by
        # ``_map_compute_error``. No cross-backend fallback: the local Numberbatch
        # model is only used through backend: local (the default), never swapped
        # in under the API path.
        return compute_similarity(alg, bck, input_data, params)

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"text_a": item.a, "text_b": item.b},
        _compute,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})


# ─── POST /v1/similarity/text/retrieval — retrieval ──────────────────────────


@app.post("/v1/similarity/text/retrieval")
def text_retrieval(request: RetrievalRequest) -> TextComputeResponse:
    """Rank query candidates for a batch of retrieval queries (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_RETRIEVAL_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_RETRIEVAL_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    _require_enabled(algorithm)

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"query": item.query, "candidates": item.candidates},
        compute_retrieval,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})


# ─── POST /v1/similarity/text/lexical — lexical relations ────────────────────


@app.post("/v1/similarity/text/lexical")
def text_lexical(request: LexicalRequest) -> TextComputeResponse:
    """Look up lexical relations for a batch of words (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_LEXICAL_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_LEXICAL_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    _require_enabled(algorithm)

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"word": item.word},
        compute_lexical,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})
