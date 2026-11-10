from __future__ import annotations

from collections.abc import Callable
from typing import Any

import networkx as nx
from pydantic import TypeAdapter

from app.adapters import graph_tool_adapter, igraph_adapter, networkit_adapter, networkx_adapter
from app.domain import GeneratedGraph
from app.schemas import GraphGenerationRequest, validate_graph_size
from graph_safety.limits import ResourceLimitError, check_result
from graph_safety.process import SLOTS, run_worker

Adapter = Callable[..., GeneratedGraph]
RouteKey = tuple[str, str]


ADAPTERS: dict[RouteKey, Adapter] = {
    ("barabasi_albert", "networkx"): networkx_adapter.generate_barabasi_albert,
    ("barabasi_albert", "igraph"): igraph_adapter.generate_barabasi_albert,
    ("barabasi_albert", "networkit"): networkit_adapter.generate_barabasi_albert,
    ("forest_fire", "igraph"): igraph_adapter.generate_forest_fire,
    ("erdos_renyi_gnp", "networkx"): networkx_adapter.generate_erdos_renyi_gnp,
    ("erdos_renyi_gnp", "igraph"): igraph_adapter.generate_erdos_renyi_gnp,
    ("erdos_renyi_gnp", "networkit"): networkit_adapter.generate_erdos_renyi_gnp,
    ("erdos_renyi_gnm", "networkx"): networkx_adapter.generate_erdos_renyi_gnm,
    ("erdos_renyi_gnm", "igraph"): igraph_adapter.generate_erdos_renyi_gnm,
    ("watts_strogatz", "networkx"): networkx_adapter.generate_watts_strogatz,
    ("watts_strogatz", "igraph"): igraph_adapter.generate_watts_strogatz,
    ("watts_strogatz", "networkit"): networkit_adapter.generate_watts_strogatz,
    ("configuration_model", "networkx"): networkx_adapter.generate_configuration_model,
    ("configuration_model", "igraph"): igraph_adapter.generate_configuration_model,
    ("configuration_model", "networkit"): networkit_adapter.generate_configuration_model,
    ("configuration_model", "graph_tool"): graph_tool_adapter.generate_configuration_model,
    ("stochastic_block_model", "networkx"): networkx_adapter.generate_stochastic_block_model,
    ("stochastic_block_model", "igraph"): igraph_adapter.generate_stochastic_block_model,
    ("stochastic_block_model", "graph_tool"): graph_tool_adapter.generate_stochastic_block_model,
    ("random_regular", "networkx"): networkx_adapter.generate_random_regular,
    ("random_regular", "igraph"): igraph_adapter.generate_random_regular,
    ("random_geometric", "networkx"): networkx_adapter.generate_random_geometric,
    ("random_geometric", "igraph"): igraph_adapter.generate_random_geometric,
    ("kronecker_rmat", "networkit"): networkit_adapter.generate_rmat,
    ("classic_deterministic", "networkx"): networkx_adapter.generate_classic_deterministic,
    ("classic_deterministic", "igraph"): igraph_adapter.generate_classic_deterministic,
    ("named_graph", "networkx"): networkx_adapter.generate_named_graph,
    ("named_graph", "igraph"): igraph_adapter.generate_named_graph,
    ("random_tree", "networkx"): networkx_adapter.generate_random_tree,
    ("random_tree", "igraph"): igraph_adapter.generate_random_tree,
    ("random_bipartite", "networkx"): networkx_adapter.generate_random_bipartite,
    ("random_bipartite", "igraph"): igraph_adapter.generate_random_bipartite,
    ("community_clustered", "networkx"): networkx_adapter.generate_community_clustered,
    ("community_clustered", "networkit"): networkit_adapter.generate_community_clustered,
    ("hyperbolic", "networkit"): networkit_adapter.generate_hyperbolic,
    ("chung_lu", "networkx"): networkx_adapter.generate_chung_lu,
    ("chung_lu", "networkit"): networkit_adapter.generate_chung_lu,
    ("static_fitness", "igraph"): igraph_adapter.generate_static_fitness,
    ("growing_attachment", "igraph"): igraph_adapter.generate_growing_attachment,
    ("kleinberg_small_world", "networkx"): networkx_adapter.generate_kleinberg_small_world,
    ("powerlaw_cluster", "networkx"): networkx_adapter.generate_powerlaw_cluster,
    ("geometric_threshold", "networkx"): networkx_adapter.generate_geometric_threshold,
    ("duplication_divergence", "networkx"): networkx_adapter.generate_internet_as,
    ("knn_graph", "graph_tool"): graph_tool_adapter.generate_knn_graph,
    ("triangulation", "graph_tool"): graph_tool_adapter.generate_triangulation,
    ("price_network", "graph_tool"): graph_tool_adapter.generate_price_network,
}

DIRECTED_ROUTES: frozenset[RouteKey] = frozenset(
    {
        ("barabasi_albert", "igraph"),
        ("forest_fire", "igraph"),
        ("erdos_renyi_gnp", "networkx"),
        ("erdos_renyi_gnp", "igraph"),
        ("erdos_renyi_gnp", "networkit"),
        ("erdos_renyi_gnm", "networkx"),
        ("erdos_renyi_gnm", "igraph"),
        ("stochastic_block_model", "networkx"),
        ("stochastic_block_model", "igraph"),
        ("random_regular", "igraph"),
        ("random_tree", "igraph"),
        ("random_bipartite", "networkx"),
        ("random_bipartite", "igraph"),
        ("community_clustered", "networkx"),
        ("growing_attachment", "igraph"),
        ("configuration_model", "graph_tool"),
        ("stochastic_block_model", "graph_tool"),
        ("knn_graph", "graph_tool"),
        ("price_network", "graph_tool"),
    }
)


def execute_request(request: GraphGenerationRequest) -> GeneratedGraph:
    key = (request.algorithm, request.backend)
    adapter = ADAPTERS.get(key)
    if adapter is None:
        raise RuntimeError(f"Validated request was not routed: {request.algorithm}/{request.backend}")

    params = {_snake_case(name): value for name, value in request.params.model_dump(exclude={"backend"}).items()}
    if key in DIRECTED_ROUTES:
        params["directed"] = request.output.directed

    return adapter(**params)


def execute_isolated(request: GraphGenerationRequest) -> GeneratedGraph:
    validate_graph_size(request)
    if request.backend == "graph_tool":
        if not SLOTS.acquire(blocking=False):
            raise ResourceLimitError("generation workers are busy; retry later", 503)
        try:
            return execute_request(request)
        finally:
            SLOTS.release()
    result = run_worker("primary", request.model_dump(by_alias=True))
    graph: nx.Graph[int] = nx.MultiDiGraph() if result["directed"] else nx.MultiGraph()
    graph.add_nodes_from(result["nodes"])
    graph.add_edges_from(result["edges"])
    check_result(graph.number_of_nodes(), graph.number_of_edges())
    return GeneratedGraph(graph, graph.number_of_nodes(), graph.number_of_edges(), graph.is_directed())


def worker_generate(payload: dict[str, Any]) -> dict[str, Any]:
    from app.exporters import _graph_data

    request: GraphGenerationRequest = TypeAdapter(GraphGenerationRequest).validate_python(payload)
    validate_graph_size(request)
    if request.backend == "graph_tool":
        raise ValueError("graph-tool must execute in its sidecar")
    generated = execute_request(request)
    check_result(generated.num_nodes, generated.num_edges)
    nodes, edges = _graph_data(generated)
    indices = {node: index for index, node in enumerate(nodes)}
    return {
        "nodes": list(range(len(nodes))),
        "edges": [(indices[a], indices[b]) for a, b in edges],
        "directed": generated.directed,
    }


def _snake_case(name: str) -> str:
    return "".join(f"_{character.lower()}" if character.isupper() else character for character in name).lstrip("_")
