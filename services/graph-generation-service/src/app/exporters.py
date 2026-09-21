from __future__ import annotations

import base64
import json
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Any, TypeAlias, cast
from uuid import NAMESPACE_URL, uuid5

import networkx as nx
from igraph import Graph as IgraphGraph
from networkit import Graph as NetworKitGraph

from app.domain import GeneratedGraph
from app.exceptions import GraphExportError
from app.schemas import LabelMode, OutputFormat
from graph_safety.limits import LIMITS, ResourceLimitError, check_result
from graph_safety.process import run_worker

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
NodeLabel: TypeAlias = int | str


@dataclass(frozen=True, slots=True)
class ExportedGraph:
    content: JsonValue | bytes
    media_type: str


class BoundedWriter(BytesIO):
    def write(self, data: Any) -> int:
        if self.tell() + len(data) > LIMITS.export_bytes:
            raise ResourceLimitError("export exceeds the byte limit")
        return super().write(data)


def bounded_json(value: Any) -> bytes:
    output = BoundedWriter()
    for chunk in json.JSONEncoder(allow_nan=False).iterencode(value):
        output.write(chunk.encode())
    return output.getvalue()


def export_isolated(
    generated: GeneratedGraph, *, output_format: OutputFormat, labels: LabelMode, resource_id: str
) -> ExportedGraph:
    check_result(generated.num_nodes, generated.num_edges)
    nodes, edges = _graph_data(generated)
    indices = {node: i for i, node in enumerate(nodes)}
    result = run_worker(
        "export",
        {
            "nodes": list(range(len(nodes))),
            "edges": [(indices[a], indices[b]) for a, b in edges],
            "directed": generated.directed,
            "format": output_format,
            "labels": labels,
            "id": resource_id,
        },
    )
    return ExportedGraph(base64.b64decode(result["content"]), result["media_type"])


def worker_export(payload: dict[str, Any]) -> dict[str, str]:
    graph: nx.Graph[int] = nx.MultiDiGraph() if payload["directed"] else nx.MultiGraph()
    check_result(len(payload["nodes"]), len(payload["edges"]))
    graph.add_nodes_from(payload["nodes"])
    graph.add_edges_from(payload["edges"])
    exported = export_graph(
        GeneratedGraph(graph, graph.number_of_nodes(), graph.number_of_edges(), graph.is_directed()),
        output_format=payload["format"],
        labels=payload["labels"],
        resource_id=payload["id"],
    )
    content = exported.content
    data = (
        bounded_json(content)
        if exported.media_type == "application/json"
        else content.encode()
        if isinstance(content, str)
        else content
    )
    if not isinstance(data, bytes):
        raise ValueError("invalid export content")
    if len(data) > LIMITS.export_bytes:
        raise ResourceLimitError("export exceeds the byte limit")
    return {"content": base64.b64encode(data).decode(), "media_type": exported.media_type}


def export_graph(
    generated: GeneratedGraph,
    *,
    output_format: OutputFormat,
    labels: LabelMode,
    resource_id: str,
) -> ExportedGraph:
    check_result(generated.num_nodes, generated.num_edges)
    nodes, edges = _graph_data(generated)
    node_labels = _node_labels(len(nodes), mode=labels, resource_id=resource_id)
    label_by_node = dict(zip(nodes, node_labels, strict=True))
    labeled_edges = [(label_by_node[source], label_by_node[target]) for source, target in edges]

    if output_format == "edge_list":
        return _edge_list_export(generated, node_labels, labeled_edges)
    if output_format == "adjacency":
        return _adjacency_export(generated, node_labels, labeled_edges)

    normalized = _networkx_graph(generated, node_labels, labeled_edges)
    if output_format == "graphml":
        output = BoundedWriter()
        nx.write_graphml(normalized, output, encoding="utf-8")
        return ExportedGraph(content=output.getvalue(), media_type="application/graphml+xml")
    if output_format == "gml":
        output = BoundedWriter()
        for line in nx.generate_gml(normalized):
            output.write((line + "\n").encode())
        return ExportedGraph(content=output.getvalue(), media_type="text/plain")
    if generated.directed:
        raise GraphExportError("graph6 does not support directed graphs")
    if labels != "index":
        raise GraphExportError("graph6 does not support UUID labels")
    if normalized.is_multigraph() or any(a == b for a, b in normalized.edges()):
        raise GraphExportError("graph6 does not support parallel edges or self-loops")

    return ExportedGraph(content=nx.to_graph6_bytes(normalized, header=False), media_type="application/octet-stream")


def _graph_data(
    generated: GeneratedGraph,
) -> tuple[Sequence[Hashable], Sequence[tuple[Hashable, Hashable]]]:
    graph = generated.graph
    if isinstance(graph, (nx.MultiGraph, nx.MultiDiGraph)):
        return list(graph.nodes), [(source, target) for source, target, _key in graph.edges(keys=True)]
    if isinstance(graph, nx.Graph):
        if graph.is_multigraph():
            multiedges = cast(Iterable[tuple[Hashable, Hashable, Any]], graph.edges)
            flat_edges: list[tuple[Hashable, Hashable]] = [(u, v) for u, v, _key in multiedges]
            return list(graph.nodes), flat_edges
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
    edges: list[tuple[NodeLabel, NodeLabel]],
) -> ExportedGraph:
    content: JsonValue = {
        "format": "edge_list",
        "directed": generated.directed,
        "nodes": list(nodes),
        "edges": [[source, target] for source, target in edges],
    }
    return ExportedGraph(content=content, media_type="application/json")


def _adjacency_export(
    generated: GeneratedGraph,
    nodes: list[NodeLabel],
    edges: list[tuple[NodeLabel, NodeLabel]],
) -> ExportedGraph:
    position = {node: index for index, node in enumerate(nodes)}
    neighbors: list[list[NodeLabel]] = [[] for _node in nodes]
    for source, target in edges:
        neighbors[position[source]].append(target)
        if not generated.directed and source != target:
            neighbors[position[target]].append(source)

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
    nodes: list[NodeLabel],
    edges: list[tuple[NodeLabel, NodeLabel]],
) -> nx.Graph[NodeLabel]:
    graph: nx.Graph[NodeLabel]
    graph = nx.MultiDiGraph() if generated.directed else nx.MultiGraph()

    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    simple = nx.DiGraph(graph) if generated.directed else nx.Graph(graph)
    if graph.number_of_edges() == simple.number_of_edges():
        return simple
    return graph
