from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Body, FastAPI, Query, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.catalog import ALGORITHM_CATALOG
from app.domain import GeneratedGraph
from app.exceptions import (
    GraphExportError,
    graph_export_exception_handler,
    request_validation_exception_handler,
)
from app.exporters import ExportedGraph, export_graph
from app.openapi import install_openapi_schema
from app.routing import execute_request
from app.schemas import (
    AlgorithmCatalogResponse,
    GraphGenerationRequest,
    GraphLinks,
    GraphMetadata,
    GraphResource,
    OutputFormat,
    ProblemDetails,
    RequestParameterError,
    validate_graph_size,
)
from app.storage import StoredGraph

GRAPH_STORE: dict[str, StoredGraph] = {}
MAX_STORED_GRAPHS = 100

app = FastAPI(
    title="Unified Graph Generation Service",
    description="Strictly validated graph-generation API with backend-specific adapter routing.",
    version="0.1.0",
)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(GraphExportError, graph_export_exception_handler)
install_openapi_schema(app)


@app.get(
    "/v1/algorithms",
    response_model=AlgorithmCatalogResponse,
    tags=["Algorithms"],
    summary="List supported graph generation algorithms and backend parameter schemas",
)
def list_algorithms() -> AlgorithmCatalogResponse:
    return AlgorithmCatalogResponse(
        algorithms=ALGORITHM_CATALOG,
        schemas=app.openapi()["components"]["schemas"],
    )


def _dump_params(params: BaseModel) -> dict[str, Any]:
    return params.model_dump(by_alias=True, exclude={"backend"})


def _graph_resource(
    request: GraphGenerationRequest,
    generated: GeneratedGraph,
    generation_time_ms: int,
) -> GraphResource:
    graph_id = f"grf_{uuid4().hex}"
    export_format = request.output.format
    return GraphResource(
        id=graph_id,
        status="completed",
        algorithm=request.algorithm,
        backend=request.backend,
        params=_dump_params(request.params),
        metadata=GraphMetadata(
            numNodes=generated.num_nodes,
            numEdges=generated.num_edges,
            directed=generated.directed,
            createdAt=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            generationTimeMs=generation_time_ms,
        ),
        _links=GraphLinks(
            self=f"/v1/graphs/{graph_id}",
            export=f"/v1/graphs/{graph_id}?format={export_format}",
        ),
    )


@app.post(
    "/v1/graphs",
    response_model=GraphResource,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "model": ProblemDetails,
            "description": "Request validation failed.",
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                },
            },
        },
    },
    tags=["Graphs"],
    summary="Generate a graph using a backend-specific algorithm adapter",
)
def create_graph(
    request: Annotated[GraphGenerationRequest, Body(discriminator="algorithm")],
) -> GraphResource:
    try:
        validate_graph_size(request)
    except RequestParameterError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "params"),
                    "msg": f"Value error, {exc}",
                    "input": request.params.model_dump(),
                    "ctx": {"error": exc},
                }
            ]
        ) from exc

    started_at = perf_counter()
    generated = execute_request(request)
    generation_time_ms = int((perf_counter() - started_at) * 1000)

    resource = _graph_resource(request, generated, generation_time_ms)
    if len(GRAPH_STORE) >= MAX_STORED_GRAPHS:
        GRAPH_STORE.pop(next(iter(GRAPH_STORE)))
    GRAPH_STORE[resource.id] = StoredGraph(
        resource=resource,
        generated=generated,
        labels=request.output.labels,
    )
    return resource


def _graph_not_found(graph_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        media_type="application/problem+json",
        content={
            "type": "https://api.aladin.local/problems/graph-not-found",
            "title": "Graph not found",
            "status": 404,
            "detail": f"No graph resource exists for id '{graph_id}'.",
            "instance": f"/v1/graphs/{graph_id}",
            "invalidParams": [{"name": "graphId", "reason": "Unknown graph resource id."}],
        },
    )


@app.get(
    "/v1/graphs/{graphId}",
    response_model=GraphResource,
    responses={
        200: {
            "description": "Graph metadata or the requested graph serialization.",
            "content": {
                "application/json": {},
                "application/graphml+xml": {"schema": {"type": "string"}},
                "text/plain": {"schema": {"type": "string"}},
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        400: {
            "model": ProblemDetails,
            "description": "The requested graph serialization is not valid for this resource.",
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                },
            },
        },
        404: {
            "model": ProblemDetails,
            "description": "Graph resource was not found.",
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                },
            },
        },
    },
    tags=["Graphs"],
    summary="Retrieve a generated graph resource",
)
def get_graph(
    graphId: str,
    output_format: Annotated[OutputFormat | None, Query(alias="format")] = None,
) -> GraphResource | Response:
    stored = GRAPH_STORE.get(graphId)
    if stored is None:
        return _graph_not_found(graphId)

    if output_format is None:
        return stored.resource

    exported = export_graph(
        stored.generated,
        output_format=output_format,
        labels=stored.labels,
        resource_id=graphId,
    )
    return _export_response(exported)


def _export_response(exported: ExportedGraph) -> Response:
    if exported.media_type == "application/json":
        return JSONResponse(content=exported.content)

    if not isinstance(exported.content, (bytes, str)):
        raise TypeError("Non-JSON graph exports must contain text or bytes")

    return StreamingResponse(_content_chunks(exported.content), media_type=exported.media_type)


def _content_chunks(content: bytes | str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    encoded = content.encode("utf-8") if isinstance(content, str) else content
    for offset in range(0, len(encoded), chunk_size):
        yield encoded[offset : offset + chunk_size]


@app.delete(
    "/v1/graphs/{graphId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        404: {
            "model": ProblemDetails,
            "description": "Graph resource was not found.",
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                },
            },
        },
    },
    tags=["Graphs"],
    summary="Release a generated graph resource",
)
def delete_graph(graphId: str) -> Response:
    if graphId not in GRAPH_STORE:
        return _graph_not_found(graphId)

    del GRAPH_STORE[graphId]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
