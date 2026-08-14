"""FastAPI application for the Text Similarity Service.

Mirrors the edit-distance-service API style: flat, synchronous, stateless
endpoints. Every compute request takes ``algorithm`` (+ optional ``backend``,
the default backend is auto-selected), ``params`` and a batch ``inputs`` list,
and returns the results synchronously.
"""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .catalog import CATALOG
from .dkpro_proxy import compute_via_sidecar, is_dkpro_request
from .lexical import DEFAULT_LEXICAL_BACKENDS, compute_lexical
from .models import (
    LexicalRequest,
    RetrievalRequest,
    TextComputeResponse,
    TextDistanceRequest,
    TextResult,
)
from .retrieval import DEFAULT_RETRIEVAL_BACKENDS, compute_retrieval
from .similarity import DEFAULT_BACKENDS, SIMILARITY_DISPATCH, compute_similarity

app = FastAPI(
    title="Text Similarity Service",
    version="0.1.0",
    description="Unified REST API for semantic text similarity — 16 algorithm families over multiple backends.",
)


# ─── Error Handler ────────────────────────────────────────────────────────────

# Missing optional module -> which pip extra enables it (used for the 501 body).
_MODULE_EXTRA = {"wn": "de"}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return an RFC 9457 application/problem+json body for every HTTP error."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail or str(exc.status_code),
            "status": exc.status_code,
            "detail": exc.detail or "",
        },
    )


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": "text-similarity-service"}


# ─── Discovery ────────────────────────────────────────────────────────────────


@app.get("/v1/text/algorithms")
async def list_algorithms() -> list[dict]:
    """Discovery: list all algorithm/backend combinations with metadata."""
    return CATALOG


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_backend(defaults: dict[str, str], algorithm: str, backend: str | None) -> str:
    """Auto-select the default backend when the caller omits ``backend``."""
    return backend or defaults.get(algorithm, "")


def _run_batch(
    algorithm: str,
    backend: str,
    params: dict[str, Any],
    inputs: list[Any],
    make_input: Callable[[Any], dict[str, Any]],
    compute_fn: Callable[[str, str, dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> tuple[list[TextResult], float]:
    """Compute a batch of inputs, mapping each item to a TextResult.

    Errors map to problem+json: validation errors -> 400, DKPro sidecar
    failures -> 502/503, everything else -> 500.
    """
    results: list[TextResult] = []
    total_ms = 0.0
    for item in inputs:
        input_data = make_input(item)
        try:
            res = compute_fn(algorithm, backend, input_data, params)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        except ModuleNotFoundError as e:
            module_name = e.name or "unknown"
            extra = _MODULE_EXTRA.get(module_name, "model")
            raise HTTPException(
                status_code=501,
                detail=(
                    f"Algorithm '{algorithm}' requires the optional '{extra}' extra "
                    f"(missing module '{module_name}'). Install it with: pip install -e '.[{extra}]'"
                ),
            ) from None
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Computation error: {e!s}") from None
        total_ms += res.get("compute_time_ms", 0)
        results.append(TextResult(id=item.id, result=res))
    return results, round(total_ms, 2)


# ─── POST /v1/text/distance — text similarity ────────────────────────────────


@app.post("/v1/text/distance")
async def text_distance(request: TextDistanceRequest) -> TextComputeResponse:
    """Compute similarity scores for a batch of text pairs (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    if (algorithm, backend) not in SIMILARITY_DISPATCH and not is_dkpro_request(algorithm, backend):
        supported = [b for (m, b) in SIMILARITY_DISPATCH if m == algorithm]
        raise HTTPException(
            status_code=400,
            detail=f"Backend '{backend}' not supported for algorithm '{algorithm}'. Supported: {supported}",
        )

    def _compute(alg: str, bck: str, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        if (alg, bck) in SIMILARITY_DISPATCH:
            return compute_similarity(alg, bck, input_data, params)
        try:
            return compute_via_sidecar(alg, params.get("variant"), input_data, params)
        except Exception as e:  # noqa: BLE001
            status = 503 if "connect" in str(e).lower() or "unreachable" in str(e).lower() else 502
            raise HTTPException(status_code=status, detail=f"DKPro sidecar request failed: {e!s}") from None

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"text_a": item.a, "text_b": item.b},
        _compute,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})


# ─── POST /v1/text/retrieval — retrieval ─────────────────────────────────────


@app.post("/v1/text/retrieval")
async def text_retrieval(request: RetrievalRequest) -> TextComputeResponse:
    """Rank query candidates for a batch of retrieval queries (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_RETRIEVAL_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_RETRIEVAL_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"query": item.query, "candidates": item.candidates},
        compute_retrieval,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})


# ─── POST /v1/text/lexical — lexical relations ───────────────────────────────


@app.post("/v1/text/lexical")
async def text_lexical(request: LexicalRequest) -> TextComputeResponse:
    """Look up lexical relations for a batch of words (synchronous)."""
    algorithm = request.algorithm
    backend = _resolve_backend(DEFAULT_LEXICAL_BACKENDS, algorithm, request.backend)

    if algorithm not in DEFAULT_LEXICAL_BACKENDS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{algorithm}'")

    results, total_ms = _run_batch(
        algorithm,
        backend,
        request.params,
        request.inputs,
        lambda item: {"word": item.word},
        compute_lexical,
    )
    return TextComputeResponse(algorithm=algorithm, backend=backend, results=results, meta={"compute_time_ms": total_ms})
