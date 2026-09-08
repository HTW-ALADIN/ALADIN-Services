from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import TypeAlias, cast
from uuid import NAMESPACE_URL, uuid5

import networkx as nx
from igraph import Graph as IgraphGraph
from networkit import Graph as NetworKitGraph

from app.domain import GeneratedGraph
from app.exceptions import GraphExportError
from app.schemas import LabelMode, OutputFormat

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
NodeLabel: TypeAlias = int | str


@dataclass(frozen=True, slots=True)
class ExportedGraph:
    content: JsonValue | bytes
    media_type: str


def export_graph(
    generated: GeneratedGraph,
    *,
    output_format: OutputFormat,
    labels: LabelMode,
    resource_id: str,
) -> ExportedGraph:
    nodes, edges = _graph_data(generated)
    node_labels = _node_labels(len(nodes), mode=labels, resource_id=resource_id)
    label_by_node = dict(zip(nodes, node_labels, strict=True))

    if output_format == "edge_list":
        return _edge_list_export(generated, node_labels, edges, label_by_node)
    if output_format == "adjacency":
        return _adjacency_export(generated, node_labels, edges, label_by_node)

    normalized = _networkx_graph(generated, node_labels, edges, label_by_node)
    if output_format == "graphml":
        output = BytesIO()
        nx.write_graphml(normalized, output, encoding="utf-8")
        return ExportedGraph(content=output.getvalue(), media_type="application/graphml+xml")
    if output_format == "gml":
        content = "\n".join(nx.generate_gml(normalized)) + "\n"
        return ExportedGraph(content=content, media_type="text/plain")
    if generated.directed:
        raise GraphExportError("graph6 does not support directed graphs")
    if labels != "index":
        raise GraphExportError("graph6 does not support UUID labels")
    if isinstance(normalized, (nx.MultiGraph, nx.MultiDiGraph)):
        raise GraphExportError("graph6 does not support multigraphs")

    return ExportedGraph(content=nx.to_graph6_bytes(normalized, header=False), media_type="application/octet-stream")


def _graph_data(
    generated: GeneratedGraph,
) -> tuple[Sequence[Hashable], Sequence[tuple[Hashable, Hashable]]]:
    graph = generated.graph
    if isinstance(graph, (nx.MultiGraph, nx.MultiDiGraph)):
        return list(graph.nodes), [(source, target) for source, target, _key in graph.edges(keys=True)]
    if isinstance(graph, nx.Graph):
        return list(graph.nodes), list(cast(Iterable[tuple[Hashable, Hashable]], graph.edges))
    if isinstance(graph, IgraphGraph):
        nodes = list(range(graph.vcount()))
        edges = cast(list[tuple[int, int]], graph.get_edgelist())
        return nodes, edges
    if isinstance(graph, NetworKitGraph):
        nodes = list(cast(Iterable[int], graph.iterNodes()))
        edges = list(cast(Iterable[tuple[int, int]], graph.iterEdges()))
        return nodes, edges

    raise TypeError(f"Unsupported graph object: {type(graph).__name__}")


def _node_labels(count: int, *, mode: LabelMode, resource_id: str) -> list[NodeLabel]:
    if mode == "index":
        return list(range(count))

    namespace = uuid5(NAMESPACE_URL, resource_id)
    return [str(uuid5(namespace, str(index))) for index in range(count)]


def _edge_list_export(
    generated: GeneratedGraph,
    nodes: list[NodeLabel],
    edges: Sequence[tuple[Hashable, Hashable]],
    label_by_node: dict[Hashable, NodeLabel],
) -> ExportedGraph:
    content: JsonValue = {
        "format": "edge_list",
        "directed": generated.directed,
        "nodes": list(nodes),
        "edges": [[label_by_node[source], label_by_node[target]] for source, target in edges],
    }
    return ExportedGraph(content=content, media_type="application/json")


def _adjacency_export(
    generated: GeneratedGraph,
    nodes: list[NodeLabel],
    edges: Sequence[tuple[Hashable, Hashable]],
    label_by_node: dict[Hashable, NodeLabel],
) -> ExportedGraph:
    position = {node: index for index, node in enumerate(nodes)}
    neighbors: list[list[NodeLabel]] = [[] for _node in nodes]
    for source, target in edges:
        source_label = label_by_node[source]
        target_label = label_by_node[target]
        neighbors[position[source_label]].append(target_label)
        if not generated.directed and source != target:
            neighbors[position[target_label]].append(source_label)

    content: JsonValue = {
        "format": "adjacency",
        "directed": generated.directed,
        "nodes": [
            {"id": node, "neighbors": list(node_neighbors)}
            for node, node_neighbors in zip(nodes, neighbors, strict=True)
        ],
    }
    return ExportedGraph(content=content, media_type="application/json")


def _networkx_graph(
    generated: GeneratedGraph,
    node_labels: list[NodeLabel],
    edges: Sequence[tuple[Hashable, Hashable]],
    label_by_node: dict[Hashable, NodeLabel],
) -> nx.Graph[NodeLabel]:
    source = generated.graph
    if isinstance(source, nx.Graph) and source.is_directed() == generated.directed:
        if list(source.nodes) == node_labels:
            return source

    is_multi = isinstance(source, (nx.MultiGraph, nx.MultiDiGraph))
    graph: nx.Graph[NodeLabel]
    if generated.directed:
        graph = nx.MultiDiGraph() if is_multi else nx.DiGraph()
    else:
        graph = nx.MultiGraph() if is_multi else nx.Graph()

    graph.add_nodes_from(node_labels)
    graph.add_edges_from((label_by_node[u], label_by_node[v]) for u, v in edges)
    return graph
