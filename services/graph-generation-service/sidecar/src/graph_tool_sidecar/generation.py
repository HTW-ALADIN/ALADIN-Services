from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from graph_safety.limits import LIMITS, ResourceLimitError
from graph_safety.process import run_worker
from graph_tool_sidecar.models import SidecarGraph, SidecarRequest


def generate_isolated(request: SidecarRequest) -> SidecarGraph:
    return SidecarGraph.model_validate(run_worker("sidecar", request.model_dump()))


def worker_generate(payload: dict[str, Any]) -> dict[str, Any]:
    from pydantic import TypeAdapter

    from app.schemas import GraphGenerationRequest, validate_graph_size

    request = SidecarRequest.model_validate(payload)
    public: GraphGenerationRequest = TypeAdapter(GraphGenerationRequest).validate_python(
        {
            "algorithm": request.algorithm,
            "backend": "graph_tool",
            "params": request.params,
            "output": {"directed": request.directed},
        }
    )
    validate_graph_size(public)
    request.params = public.params.model_dump(by_alias=True, exclude={"backend"})
    return generate(request).model_dump()


class _Vertex(Protocol):
    def __int__(self) -> int: ...


class _Edge(Protocol):
    def source(self) -> _Vertex: ...

    def target(self) -> _Vertex: ...


class _Graph(Protocol):
    def num_vertices(self) -> int: ...

    def edges(self) -> Any: ...

    def is_directed(self) -> bool: ...


def generate(request: SidecarRequest) -> SidecarGraph:
    graph_tool = import_module("graph_tool")
    generation = import_module("graph_tool.generation")
    params = request.params
    seed = params.get("seed")
    if isinstance(seed, int):
        graph_tool.seed_rng(seed)

    if request.algorithm == "configuration_model":
        graph = _configuration_model(generation, params, directed=request.directed)
    elif request.algorithm == "stochastic_block_model":
        graph = _stochastic_block_model(generation, params, directed=request.directed)
    elif request.algorithm == "knn_graph":
        graph, _weights = generation.generate_knn(
            _points(params),
            int(params["k"]),
            exact=bool(params.get("exact", False)),
            r=float(params.get("r", 0.5)),
            epsilon=float(params.get("epsilon", 0.001)),
            max_iter=int(params.get("maxIter", 0)),
            directed=request.directed,
        )
    elif request.algorithm == "triangulation":
        graph, _positions = generation.triangulation(
            _points(params),
            type=str(params.get("type", "simple")),
            periodic=bool(params.get("periodic", False)),
        )
    else:
        kwargs: dict[str, Any] = {
            "N": int(params["n"]),
            "m": int(params.get("m", 1)),
            "gamma": float(params.get("gamma", 1.0)),
            "directed": request.directed,
        }
        if params.get("c") is not None:
            kwargs["c"] = float(params["c"])
        graph = generation.price_network(**kwargs)

    return _normalize(cast(_Graph, graph))


def _configuration_model(generation: Any, params: dict[str, Any], *, directed: bool) -> Any:
    out_sequence = [int(value) for value in params["out"]]
    in_sequence = params.get("in")
    if directed:
        if not isinstance(in_sequence, list):
            raise ValueError("directed configuration_model requires params.in")
        typed_in = [int(value) for value in in_sequence]

        def directed_degree_sampler(index: int) -> tuple[int, int]:
            return typed_in[index], out_sequence[index]

        degree_sampler: Callable[[int], int | tuple[int, int]] = directed_degree_sampler
    else:

        def undirected_degree_sampler(index: int) -> int:
            return out_sequence[index]

        degree_sampler = undirected_degree_sampler

    return generation.random_graph(
        len(out_sequence),
        degree_sampler,
        directed=directed,
        parallel_edges=bool(params.get("parallelEdges", False)),
        self_loops=bool(params.get("selfLoops", False)),
        random=bool(params.get("random", True)),
    )


def _stochastic_block_model(generation: Any, params: dict[str, Any], *, directed: bool) -> Any:
    membership = np.asarray(params["membership"], dtype=np.int64)
    matrix = np.asarray(params["matrix"], dtype=float)
    out_degrees = _optional_array(params.get("outDegrees"))
    in_degrees = _optional_array(params.get("inDegrees"))
    if params.get("variant", "poisson") == "maxent":
        if not (out_degrees is not None):
            raise ValueError("required graph parameters are missing")
        return generation.generate_maxent_sbm(
            membership,
            matrix,
            out_degrees,
            in_degrees,
            directed=directed,
            multigraph=bool(params.get("multigraph", False)),
            self_loops=bool(params.get("selfLoops", False)),
        )
    return generation.generate_sbm(
        membership,
        matrix,
        out_degrees,
        in_degrees,
        directed=directed,
        micro_ers=bool(params.get("microErs", False)),
        micro_degs=bool(params.get("microDegs", False)),
    )


def _points(params: dict[str, Any]) -> NDArray[np.float64]:
    raw_points = params.get("points")
    if isinstance(raw_points, list):
        return np.asarray(raw_points, dtype=float)

    generator = params.get("pointGenerator")
    if not isinstance(generator, dict):
        raise ValueError("points or pointGenerator is required")
    rng = np.random.default_rng(generator.get("seed"))
    return rng.uniform(
        low=float(generator.get("low", 0.0)),
        high=float(generator.get("high", 1.0)),
        size=(int(generator["n"]), int(generator.get("dimensions", 2))),
    )


def _optional_array(value: object) -> NDArray[np.float64] | None:
    return None if value is None else np.asarray(value, dtype=float)


def _normalize(graph: _Graph) -> SidecarGraph:
    if graph.num_vertices() > LIMITS.nodes:
        raise ResourceLimitError("generated graph exceeds the node limit")
    nodes = list(range(graph.num_vertices()))
    edges: list[tuple[int, int]] = []
    for edge in cast(Any, graph.edges()):
        if len(edges) >= LIMITS.edges:
            raise ResourceLimitError("generated graph exceeds the edge limit")
        edges.append((int(cast(_Edge, edge).source()), int(cast(_Edge, edge).target())))
    return SidecarGraph(nodes=nodes, edges=edges, directed=graph.is_directed())
