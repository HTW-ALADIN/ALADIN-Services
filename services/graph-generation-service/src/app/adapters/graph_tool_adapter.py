from __future__ import annotations

import json
import os
from math import isfinite
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import networkx as nx
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.domain import GeneratedGraph
from app.exceptions import GraphBackendError
from graph_safety.limits import LIMITS, ResourceLimitError, check_result


class _SidecarGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[int]
    edges: list[tuple[int, int]]
    directed: bool

    @model_validator(mode="after")
    def validate_edges(self) -> _SidecarGraph:
        check_result(len(self.nodes), len(self.edges))
        known_nodes = set(self.nodes)
        if len(known_nodes) != len(self.nodes):
            raise ValueError("sidecar returned duplicate node identifiers")
        if any(source not in known_nodes or target not in known_nodes for source, target in self.edges):
            raise ValueError("sidecar returned an edge with an unknown endpoint")
        return self


def generate_configuration_model(
    *,
    out: list[int],
    in_: list[int] | None = None,
    parallel_edges: bool = False,
    self_loops: bool = False,
    random: bool = True,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    return _generate(
        "configuration_model",
        {
            "out": out,
            "in": in_,
            "parallelEdges": parallel_edges,
            "selfLoops": self_loops,
            "random": random,
            "seed": seed,
        },
        directed=directed,
    )


def generate_stochastic_block_model(
    *,
    variant: str,
    membership: list[int],
    matrix: list[list[float]],
    out_degrees: list[float] | None = None,
    in_degrees: list[float] | None = None,
    micro_ers: bool = False,
    micro_degs: bool = False,
    multigraph: bool = False,
    self_loops: bool = False,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    return _generate(
        "stochastic_block_model",
        {
            "variant": variant,
            "membership": membership,
            "matrix": matrix,
            "outDegrees": out_degrees,
            "inDegrees": in_degrees,
            "microErs": micro_ers,
            "microDegs": micro_degs,
            "multigraph": multigraph,
            "selfLoops": self_loops,
            "seed": seed,
        },
        directed=directed,
    )


def generate_knn_graph(
    *,
    points: list[list[float]] | None = None,
    point_generator: dict[str, Any] | None = None,
    k: int,
    exact: bool = False,
    r: float = 0.5,
    epsilon: float = 0.001,
    max_iter: int = 0,
    directed: bool = False,
) -> GeneratedGraph:
    return _generate(
        "knn_graph",
        {
            "points": points,
            "pointGenerator": point_generator,
            "k": k,
            "exact": exact,
            "r": r,
            "epsilon": epsilon,
            "maxIter": max_iter,
        },
        directed=directed,
    )


def generate_triangulation(
    *,
    points: list[list[float]] | None = None,
    point_generator: dict[str, Any] | None = None,
    type: str = "simple",
    periodic: bool = False,
) -> GeneratedGraph:
    return _generate(
        "triangulation",
        {
            "points": points,
            "pointGenerator": point_generator,
            "type": type,
            "periodic": periodic,
        },
        directed=False,
    )


def generate_price_network(
    *,
    n: int,
    m: int = 1,
    c: float | None = None,
    gamma: float = 1.0,
    seed: int | None = None,
    directed: bool = True,
) -> GeneratedGraph:
    return _generate(
        "price_network",
        {"n": n, "m": m, "c": c, "gamma": gamma, "seed": seed},
        directed=directed,
    )


def sidecar_health() -> bool:
    request = Request(f"{_sidecar_url()}/healthz", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=_sidecar_timeout()) as response:  # noqa: S310 - configured internal URL
            return getattr(response, "status", 0) == 200
    except (OSError, HTTPError, URLError):
        return False


def _generate(algorithm: str, params: dict[str, Any], *, directed: bool) -> GeneratedGraph:
    payload = json.dumps({"algorithm": algorithm, "params": params, "directed": directed}).encode("utf-8")
    request = Request(
        f"{_sidecar_url()}/v1/generate",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=_sidecar_timeout()) as response:  # noqa: S310 - configured internal URL
            body = response.read(LIMITS.result_bytes + 1)
            if len(body) > LIMITS.result_bytes:
                raise ResourceLimitError("sidecar response exceeds the byte limit")
    except HTTPError as exc:
        detail = _http_error_detail(exc)
        if exc.code in {400, 413, 503, 504}:
            raise ResourceLimitError(detail, exc.code) from exc
        raise GraphBackendError("graph_tool", detail, status_code=502) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise GraphBackendError("graph_tool", "graph-tool sidecar is unavailable", status_code=503) from exc

    try:
        normalized = _SidecarGraph.model_validate_json(body)
    except ValidationError as exc:
        raise GraphBackendError(
            "graph_tool", "graph-tool sidecar returned an invalid response", status_code=502
        ) from exc

    graph: nx.Graph[int]
    if normalized.directed != directed:
        raise GraphBackendError("graph_tool", "sidecar returned inconsistent directedness", status_code=502)
    graph = nx.MultiDiGraph() if normalized.directed else nx.MultiGraph()
    graph.add_nodes_from(normalized.nodes)
    graph.add_edges_from(normalized.edges)
    return GeneratedGraph(
        graph=graph,
        num_nodes=graph.number_of_nodes(),
        num_edges=graph.number_of_edges(),
        directed=graph.is_directed(),
    )


def _sidecar_url() -> str:
    url = os.environ.get("GRAPH_TOOL_SIDECAR_URL", "http://graph-tool-sidecar:8003").rstrip("/")
    if urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).hostname:
        raise ValueError("GRAPH_TOOL_SIDECAR_URL must be an HTTP(S) URL")
    return url


def _sidecar_timeout() -> float:
    timeout = float(os.environ.get("GRAPH_TOOL_SIDECAR_TIMEOUT_SECONDS", str(LIMITS.seconds + 10)))
    if not isfinite(timeout) or timeout <= 0:
        raise ValueError("GRAPH_TOOL_SIDECAR_TIMEOUT_SECONDS must be finite and positive")
    return timeout


def _http_error_detail(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read(LIMITS.result_bytes + 1))
    except (json.JSONDecodeError, OSError):
        return f"graph-tool sidecar failed with HTTP {exc.code}"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return detail if isinstance(detail, str) else f"graph-tool sidecar failed with HTTP {exc.code}"
