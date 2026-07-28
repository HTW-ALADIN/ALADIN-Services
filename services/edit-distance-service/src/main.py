"""FastAPI application for the Edit Distance Service."""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .graph import GED_ALGORITHM_CATALOG, compute_ged
from .models import (
    GedResultResponse,
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


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ProblemDetail(
            title=exc.detail or str(exc.status_code),
            status=exc.status_code,
            detail=exc.detail or "",
        ).model_dump(),
    )


# ─── PART A: Text Edit Distance ───────────────────────────────────────────────


@app.get("/v1/text/algorithms")
async def list_text_algorithms() -> list[dict]:
    """Discovery: list all algorithm/backend combinations with metadata."""
    return TEXT_ALGORITHM_CATALOG


@app.post("/v1/text/distance")
async def text_distance(request: dict[str, Any]) -> TextCompareResponse:
    """Compute a distance/similarity/transform for one pair or a batch of pairs.

    The request body is a discriminated union keyed by 'algorithm'.
    See the /v1/text/algorithms endpoint for the full catalog of supported
    algorithm/backend combinations and their parameter schemas.
    """
    algorithm = request.get("algorithm")
    if not algorithm:
        raise HTTPException(
            status_code=400, detail="Missing required field: 'algorithm'"
        )

    backend = _get_default_backend(algorithm)
    params = request.get("params", {})
    raw_inputs = request.get("inputs", [])

    if not raw_inputs:
        raise HTTPException(status_code=400, detail="Missing required field: 'inputs'")

    # Handle phonetic encoding separately (different input shape)
    if algorithm == "phonetic_encoding":
        from .models import InputPhonetic

        inputs = [InputPhonetic(**inp) for inp in raw_inputs]
    else:
        from .models import InputPair

        inputs = [InputPair(**inp) for inp in raw_inputs]

    try:
        results, result_type, compute_ms = compute_text(
            algorithm, backend, inputs, params
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Computation error: {e!s}")

    return TextCompareResponse(
        algorithm=algorithm,
        backend=backend,
        result_type=result_type,
        results=results,
        meta={"compute_time_ms": round(compute_ms, 2)},
    )


def _get_default_backend(algorithm: str) -> str:
    """Return the default backend for a given algorithm."""
    defaults = {
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
    return defaults.get(algorithm, "rapidfuzz")


# ─── PART B: Graph Edit Distance ──────────────────────────────────────────────


@app.get("/v1/graphs/algorithms")
async def list_ged_algorithms() -> list[dict]:
    """Discovery: list all GED algorithm/backend/method combinations."""
    return GED_ALGORITHM_CATALOG


_GED_DEFAULT_BACKEND = {
    "ged_astar": "networkx",
    "ged_heuristic": "gedlib",
    "ged_hausdorff": "gmatch4py",
    "ged_greedy": "gmatch4py",
}


@app.post("/v1/graphs/distance")
async def ged_compute(request: dict[str, Any]) -> JSONResponse:
    """Compute the edit distance between one pair (or a batch of pairs) of graphs."""
    algorithm = request.get("algorithm")
    if not algorithm:
        raise HTTPException(
            status_code=400, detail="Missing required field: 'algorithm'"
        )

    backend = _GED_DEFAULT_BACKEND.get(algorithm, "networkx")
    params = request.get("params", {})
    raw_graphs = request.get("graphs", [])

    if not raw_graphs:
        raise HTTPException(status_code=400, detail="Missing required field: 'graphs'")

    from .models import GraphPair

    graphs = [GraphPair(**g) for g in raw_graphs]

    try:
        results = compute_ged(algorithm, backend, graphs, params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Computation error: {e!s}")

    result_id = f"ged_{uuid.uuid4().hex[:12]}"
    response = GedResultResponse(
        id=result_id,
        status="completed",
        algorithm=algorithm,
        backend=backend,
        params=params,
        results=results,
    )

    return Response(
        content=response.model_dump_json(),
        status_code=201,
        media_type="application/json",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "edit-distance-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
