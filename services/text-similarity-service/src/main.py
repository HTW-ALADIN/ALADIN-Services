"""FastAPI application for the Text Similarity Service."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import (
    similarity_spec_b,  # noqa: F401  (registers Spec B measures in dispatchers)
    similarity_spec_c,  # noqa: F401  (registers Spec C measures in dispatchers)
)
from .catalog import get_catalog
from .dkpro_proxy import compute_via_sidecar, is_dkpro_request
from .lexical import DEFAULT_LEXICAL_BACKENDS, LEXICAL_DISPATCH, compute_lexical
from .models import (
    ComputeRequest,
    ResultLinks,
    ResultMetadata,
    ResultResponse,
)
from .retrieval import DEFAULT_RETRIEVAL_BACKENDS, RETRIEVAL_DISPATCH, compute_retrieval
from .similarity import DEFAULT_BACKENDS, SIMILARITY_DISPATCH, compute_similarity

app = FastAPI(
    title="Text Similarity Service",
    version="0.1.0",
    description="Unified REST API for text similarity — 23 algorithm families over 8 backends (Spec C / full coverage).",
)


# ─── In-memory result store ───────────────────────────────────────────────────

_results: dict[str, dict[str, Any]] = {}


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


def _problem_response(status: int, title: str, detail: str, invalid_params: list[dict[str, str]] | None = None) -> JSONResponse:
    """Build an RFC 9457 application/problem+json response."""
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if invalid_params:
        body["invalidParams"] = [{"name": p["name"], "reason": p["reason"]} for p in invalid_params]
    return JSONResponse(status_code=status, content=body)


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": "text-similarity-service"}


# ─── API Endpoints ────────────────────────────────────────────────────────────


@app.get("/v1/measures")
async def list_measures():
    """Discovery: list all operation/measure/backend combinations with metadata."""
    return get_catalog(spec="C")


@app.post("/v1/compute")
async def compute(body: ComputeRequest, background_tasks: BackgroundTasks):
    """Run a computation. Returns 201 (sync) or 202 (async) with a Result resource."""
    # Validate operation
    valid_ops = {"similarity", "retrieval", "lexical_relations"}
    if body.operation not in valid_ops:
        return _problem_response(
            status=400,
            title="Invalid operation",
            detail=f"Unknown operation '{body.operation}'. Must be one of: {', '.join(sorted(valid_ops))}",
            invalid_params=[{"name": "operation", "reason": f"Must be one of: {', '.join(sorted(valid_ops))}"}],
        )

    # Validate operation-specific required fields
    if body.operation == "similarity" and not body.measure:
        return _problem_response(
            status=400,
            title="Missing measure",
            detail="Field 'measure' is required for operation 'similarity'",
            invalid_params=[{"name": "measure", "reason": "Required for operation 'similarity'"}],
        )
    if body.operation == "retrieval" and not body.method:
        return _problem_response(
            status=400,
            title="Missing method",
            detail="Field 'method' is required for operation 'retrieval'",
            invalid_params=[{"name": "method", "reason": "Required for operation 'retrieval'"}],
        )
    if body.operation == "lexical_relations" and not body.relation:
        return _problem_response(
            status=400,
            title="Missing relation",
            detail="Field 'relation' is required for operation 'lexical_relations'",
            invalid_params=[{"name": "relation", "reason": "Required for operation 'lexical_relations'"}],
        )

    # Route to handler based on operation
    if body.operation == "similarity":
        return await _handle_similarity(body, background_tasks)
    elif body.operation == "retrieval":
        return await _handle_retrieval(body)
    elif body.operation == "lexical_relations":
        return await _handle_lexical(body)

    raise HTTPException(status_code=501, detail="Not implemented")


def _store_result(result_id: str, response: ResultResponse) -> None:
    """Store a completed result in the in-memory store."""
    _results[result_id] = response.model_dump(by_alias=True)


def _run_async_computation(result_id: str, measure: str, backend: str, input_data: dict[str, Any], params: dict[str, Any]) -> None:
    """Background task: run computation and update the stored result status."""
    try:
        result = compute_similarity(measure, backend, input_data, params)
        now = datetime.now(UTC).isoformat()
        stored = _results[result_id]
        stored["status"] = "completed"
        stored["result"] = result
        stored["metadata"]["computeTimeMs"] = result.get("compute_time_ms", 0)
        stored["metadata"]["createdAt"] = now
    except Exception as e:  # noqa: BLE001
        stored = _results.get(result_id)
        if stored is not None:
            stored["status"] = "failed"
            stored["result"] = {"error": str(e)}


async def _handle_similarity(body: ComputeRequest, background_tasks: BackgroundTasks) -> JSONResponse:
    """Handle a similarity computation request."""
    measure = body.measure or ""
    backend = body.backend
    input_data = body.input
    params = body.params

    # Validate measure is known
    if measure not in DEFAULT_BACKENDS:
        return _problem_response(
            status=400,
            title="Unknown measure",
            detail=f"Unknown measure '{measure}'",
            invalid_params=[{"name": "measure", "reason": f"Must be one of: {', '.join(sorted(DEFAULT_BACKENDS.keys()))}"}],
        )

    # Resolve backend
    if backend is None:
        backend = DEFAULT_BACKENDS.get(measure, "nltk")

    # Validate backend is supported for this measure
    key = (measure, backend)
    if key not in SIMILARITY_DISPATCH:
        # Check if this is a DKPro sidecar measure
        if is_dkpro_request(measure, backend):
            return await _handle_dkpro_similarity(measure, backend, input_data, params)
        return _problem_response(
            status=400,
            title="Unsupported backend",
            detail=f"Backend '{backend}' not supported for measure '{measure}'",
            invalid_params=[{"name": "backend", "reason": f"Supported backends for '{measure}': {_get_supported_backends(measure)}"}],
        )

    # Check if this is an async operation
    async_measures = {"sbert_cosine", "cross_encoder", "bertscore"}
    is_async = measure in async_measures

    result_id = f"res_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    if is_async:
        # Store pending result, schedule background computation
        pending_result = ResultResponse(
            id=result_id,
            status="pending",
            operation="similarity",
            measure=measure,
            backend=backend,
            input=input_data,
            result={},
            metadata=ResultMetadata(
                symmetric=True,
                computeTimeMs=0,
                createdAt=now,
            ),
            links=ResultLinks(self=f"/v1/results/{result_id}"),
        )
        _results[result_id] = pending_result.model_dump(by_alias=True)
        background_tasks.add_task(_run_async_computation, result_id, measure, backend, input_data, params)
        return JSONResponse(status_code=202, content=pending_result.model_dump(by_alias=True))

    # Sync path: compute inline
    try:
        result = compute_similarity(measure, backend, input_data, params)
    except ValueError as e:
        return _problem_response(status=400, title="Computation error", detail=str(e))
    except Exception as e:
        return _problem_response(status=500, title="Internal error", detail=str(e))

    response = ResultResponse(
        id=result_id,
        status="completed",
        operation="similarity",
        measure=measure,
        backend=backend,
        input=input_data,
        result=result,
        metadata=ResultMetadata(
            symmetric=True,
            computeTimeMs=result.get("compute_time_ms", 0),
            createdAt=now,
        ),
        links=ResultLinks(self=f"/v1/results/{result_id}"),
    )

    # Store result
    _results[result_id] = response.model_dump(by_alias=True)
    return JSONResponse(status_code=201, content=response.model_dump(by_alias=True))


def _get_supported_backends(measure: str) -> list[str]:
    """Get list of supported backends for a measure."""
    return [b for (m, b) in SIMILARITY_DISPATCH if m == measure]


async def _handle_dkpro_similarity(measure: str, backend: str, input_data: dict[str, Any], params: dict[str, Any]) -> JSONResponse:
    """Handle a similarity computation routed to the DKPro sidecar."""
    variant = params.get("variant")

    try:
        result = compute_via_sidecar(measure, variant, input_data, params)
    except Exception as e:  # noqa: BLE001
        # Sidecar failure — surface as a clean problem+json (502/503), not a
        # raw Java stack trace.
        status = 503 if "connect" in str(e).lower() or "unreachable" in str(e).lower() else 502
        return _problem_response(
            status=status,
            title="DKPro sidecar unavailable",
            detail=f"DKPro sidecar request failed: {e!s}",
        )

    result_id = f"res_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    response = ResultResponse(
        id=result_id,
        status="completed",
        operation="similarity",
        measure=measure,
        backend="dkpro",
        input=input_data,
        result=result,
        metadata=ResultMetadata(
            symmetric=True,
            computeTimeMs=result.get("compute_time_ms", 0),
            createdAt=now,
        ),
        links=ResultLinks(self=f"/v1/results/{result_id}"),
    )

    _results[result_id] = response.model_dump(by_alias=True)
    return JSONResponse(status_code=201, content=response.model_dump(by_alias=True))


async def _handle_retrieval(body: ComputeRequest) -> JSONResponse:
    """Handle a retrieval computation request."""
    method = body.method or ""
    backend = body.backend
    input_data = body.input
    params = body.params

    if method not in DEFAULT_RETRIEVAL_BACKENDS:
        return _problem_response(
            status=400,
            title="Unknown method",
            detail=f"Unknown method '{method}'",
            invalid_params=[{"name": "method", "reason": f"Must be one of: {', '.join(sorted(DEFAULT_RETRIEVAL_BACKENDS.keys()))}"}],
        )

    if backend is None:
        backend = DEFAULT_RETRIEVAL_BACKENDS.get(method, "rapidfuzz")

    key = (method, backend)
    if key not in RETRIEVAL_DISPATCH:
        return _problem_response(
            status=400,
            title="Unsupported backend",
            detail=f"Backend '{backend}' not supported for method '{method}'",
        )

    try:
        result = compute_retrieval(method, backend, input_data, params)
    except ValueError as e:
        return _problem_response(status=400, title="Computation error", detail=str(e))
    except Exception as e:
        return _problem_response(status=500, title="Internal error", detail=str(e))

    result_id = f"res_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    response = ResultResponse(
        id=result_id,
        status="completed",
        operation="retrieval",
        measure=method,
        backend=backend,
        input=input_data,
        result=result,
        metadata=ResultMetadata(
            symmetric=False,
            computeTimeMs=result.get("compute_time_ms", 0),
            createdAt=now,
        ),
        links=ResultLinks(self=f"/v1/results/{result_id}"),
    )

    _results[result_id] = response.model_dump(by_alias=True)
    return JSONResponse(status_code=201, content=response.model_dump(by_alias=True))


async def _handle_lexical(body: ComputeRequest) -> JSONResponse:
    """Handle a lexical relations computation request."""
    relation = body.relation or ""
    backend = body.backend
    input_data = body.input
    params = body.params

    if relation not in DEFAULT_LEXICAL_BACKENDS:
        return _problem_response(
            status=400,
            title="Unknown relation",
            detail=f"Unknown relation '{relation}'",
            invalid_params=[{"name": "relation", "reason": f"Must be one of: {', '.join(sorted(DEFAULT_LEXICAL_BACKENDS.keys()))}"}],
        )

    if backend is None:
        backend = DEFAULT_LEXICAL_BACKENDS.get(relation, "nltk")

    key = (relation, backend)
    if key not in LEXICAL_DISPATCH:
        return _problem_response(
            status=400,
            title="Unsupported backend",
            detail=f"Backend '{backend}' not supported for relation '{relation}'",
        )

    try:
        result = compute_lexical(relation, backend, input_data, params)
    except ValueError as e:
        return _problem_response(status=400, title="Computation error", detail=str(e))
    except Exception as e:
        return _problem_response(status=500, title="Internal error", detail=str(e))

    result_id = f"res_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    response = ResultResponse(
        id=result_id,
        status="completed",
        operation="lexical_relations",
        measure=relation,
        backend=backend,
        input=input_data,
        result=result,
        metadata=ResultMetadata(
            symmetric=False,
            computeTimeMs=result.get("compute_time_ms", 0),
            createdAt=now,
        ),
        links=ResultLinks(self=f"/v1/results/{result_id}"),
    )

    _results[result_id] = response.model_dump(by_alias=True)
    return JSONResponse(status_code=201, content=response.model_dump(by_alias=True))


@app.get("/v1/results/{result_id}")
async def get_result(result_id: str):
    """Retrieve a previously computed result."""
    result = _results.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    return result


@app.delete("/v1/results/{result_id}", status_code=204)
async def delete_result(result_id: str):
    """Release a stored result resource."""
    if result_id not in _results:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    del _results[result_id]
    return None
