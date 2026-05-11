"""Diagramm-übergreifende Graph-Abfragen und Helfer."""
from __future__ import annotations

from collections import Counter

from src.diagrams.erd.models import Edge, Graph, Node


def count_nodes_by_type(graph: Graph) -> dict[str, int]:
    return dict(sorted(Counter(node.type for node in graph.nodes).items()))


def count_edges_by_kind(graph: Graph) -> dict[str, int]:
    return dict(sorted(Counter(edge.kind or "UNKNOWN" for edge in graph.edges).items()))


def build_index(nodes: list[Node]) -> dict[str, Node]:
    """Erzeugt einen Lookup {node.id: node}."""
    return {node.id: node for node in nodes}


def edge_pair_id(edge: Edge) -> str:
    """Erzeugt einen String-Identifier 'from->to' für eine Kante."""
    return f"{edge.from_}->{edge.to}"


def find_edge_indexes(edges: list[Edge], pair_id: str) -> list[int]:
    """Liefert alle Indizes von Kanten, die pair_id entsprechen."""
    return [i for i, e in enumerate(edges) if edge_pair_id(e) == pair_id]


def get_unique_edge(edges: list[Edge], pair_id: str) -> tuple[int, Edge] | None:
    """Liefert genau eine Kante für pair_id, None wenn keine oder mehrere matchen."""
    matches = [(i, e) for i, e in enumerate(edges) if edge_pair_id(e) == pair_id]
    if len(matches) == 1:
        return matches[0]
    return None
