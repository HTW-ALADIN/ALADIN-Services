from __future__ import annotations
from typing import TYPE_CHECKING

"""Diagramm-übergreifende Graph-Helfer."""
from collections import Counter
from typing import Any


def count_nodes_by_type(graph: Any) -> dict[str, int]:
    return dict(sorted(Counter(node.type for node in graph.nodes).items()))


def count_edges_by_kind(graph: Any) -> dict[str, int]:
    return dict(sorted(Counter(edge.kind or "UNKNOWN" for edge in graph.edges).items()))




"""
Diese Funktionen arbeiten auf allem, was Nodes mit ``id``
und Edges mit ``from_``/``to`` hat.
"""


if TYPE_CHECKING:
    from src.diagrams.erd.models import Edge, Node


def build_index(nodes: list["Node"]) -> dict[str, "Node"]:
    """Erzeugt einen Lookup {node.id: node}."""
    raise NotImplementedError


def edge_pair_id(edge: "Edge") -> str:
    """Erzeugt einen String-Identifier "from->to" für eine Kante."""
    raise NotImplementedError


def find_edge_indexes(edges: list["Edge"], pair_id: str) -> list[int]:
    """Liefert alle Indizes von Kanten, die pair_id entsprechen."""
    raise NotImplementedError


def get_unique_edge(
    edges: list["Edge"], pair_id: str
) -> tuple[int, "Edge"] | None:
    """Liefert genau eine Kante für pair_id.

    Rückgabe ist None, wenn keine oder mehrere Kanten matchen.
    """
    raise NotImplementedError
