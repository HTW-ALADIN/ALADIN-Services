"""FastAPI application for the Edit Distance Service."""

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .graph import GED_ALGORITHM_CATALOG, compute_ged
from .models import (
    GedComputeRequest,
    GedResultResponse,
    TextCompareRequest,
    TextCompareResponse,
)
from .text import ALGORITHM_CATALOG as TEXT_ALGORITHM_CATALOG
from .text import compute_text

app = FastAPI(
    title="Edit Distance Service",
    version="0.1.0",
    description="Unified microservice for text edit distance and graph edit distance algorithms.",
)


# ─── Error Handler ────────────────────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail or str(exc.status_code),
            "status": exc.status_code,
            "detail": exc.detail or "",
        },
    )


# ─── PART A: Text Edit Distance ───────────────────────────────────────────────

_DEFAULT_TEXT_BACKEND: dict[str, str] = {
    "levenshtein": "rapidfuzz",
    "damerau_levenshtein": "rapidfuzz",
    "hamming": "rapidfuzz",
    "jaro_winkler": "rapidfuzz",
    "osa": "rapidfuzz",
    "indel": "rapidfuzz",
    "lcs": "textdistance",
    "needleman_wunsch": "textdistance",
    "gotoh": "textdistance",
    "smith_waterman": "textdistance",
    "token_set_similarity": "textdistance",
    "ncd": "textdistance",
    "phonetic_encoding": "jellyfish",
    "long_sequence_alignment": "edlib",
    "diff_patch": "diff_match_patch",
}

_DEFAULT_GED_BACKEND: dict[str, str] = {
    "ged_astar": "networkx",
    # gedlib (gedlibpy) is not installed by default (no PyPI package, and
    # building it requires the full GEDLIB C++ library); gmatch4py is
    # installed by default (see Makefile/Dockerfile) and covers the
    # BIPARTITE heuristic out of the box. Callers who have manually
    # installed gedlibpy can still opt in via `"backend": "gedlib"`.
    "ged_heuristic": "gmatch4py",
    "ged_hausdorff": "gmatch4py",
    "ged_greedy": "gmatch4py",
}

# (algorithm, backend) -> the set of `params.method` values that backend
# actually implements, taken from GED_ALGORITHM_CATALOG. Used to reject
# requests for a method the *resolved* backend does not support instead of
# silently running a different method (e.g. requesting "method": "IPFP"
# without an explicit "backend" resolves to the gmatch4py default, which
# only implements BIPARTITE and would otherwise ignore "IPFP" outright).
_GED_METHOD_OPTIONS: dict[tuple[str, str], list[str]] = {
    (entry["algorithm"], entry["backend"]): entry["method_options"]
    for entry in GED_ALGORITHM_CATALOG
}

# ─── PART A: Text Edit Distance ───────────────────────────────────────────────


@app.get("/v1/text/algorithms")
async def list_text_algorithms() -> list[dict]:
    """Discovery: list all algorithm/backend combinations with metadata."""
    return TEXT_ALGORITHM_CATALOG


@app.post("/v1/text/distance")
def text_distance(request: TextCompareRequest) -> TextCompareResponse:
    """Compute a distance/similarity/transform for one pair or a batch of pairs.

    See the /v1/text/algorithms endpoint for the full catalog of supported
    algorithm/backend combinations and their parameter schemas.
    """
    algorithm = request.algorithm
    backend = request.backend or _DEFAULT_TEXT_BACKEND.get(algorithm, "rapidfuzz")
    params = request.params
    inputs = request.inputs

    if not inputs:
        raise HTTPException(status_code=400, detail="Missing required field: 'inputs'")

    try:
        results, result_type, compute_ms = compute_text(
            algorithm, backend, inputs, params
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Computation error: {e!s}")

    return TextCompareResponse(
        algorithm=algorithm,
        backend=backend,
        result_type=result_type,
        results=results,
        meta={"compute_time_ms": round(compute_ms, 2)},
    )


# ─── PART B: Graph Edit Distance ──────────────────────────────────────────────


@app.get("/v1/graphs/algorithms")
async def list_ged_algorithms() -> list[dict]:
    """Discovery: list all GED algorithm/backend/method combinations."""
    return GED_ALGORITHM_CATALOG


@app.post("/v1/graphs/distance")
def ged_compute(request: GedComputeRequest) -> GedResultResponse:
    """Compute the edit distance between one pair (or a batch of pairs) of graphs."""
    algorithm = request.algorithm
    backend = request.backend or _DEFAULT_GED_BACKEND.get(algorithm, "networkx")
    params = request.params
    graphs = request.graphs

    if not graphs:
        raise HTTPException(status_code=400, detail="Missing required field: 'graphs'")

    requested_method = params.get("method")
    if requested_method is not None:
        allowed_methods = _GED_METHOD_OPTIONS.get((algorithm, backend))
        if allowed_methods and requested_method not in allowed_methods:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported method {requested_method!r} for {algorithm}/{backend}. "
                    f"Available methods for this backend: {allowed_methods}. "
                    'If you need a gedlib-only method (e.g. "IPFP", "REFINE"), explicitly '
                    'set "backend": "gedlib" (requires gedlibpy to be manually installed).'
                ),
            )

    try:
        results = compute_ged(algorithm, backend, graphs, params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Computation error: {e!s}")

    result_id = f"ged_{uuid.uuid4().hex[:12]}"

    return GedResultResponse(
        id=result_id,
        algorithm=algorithm,
        backend=backend,
        params=params,
        results=results,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "edit-distance-service"}
