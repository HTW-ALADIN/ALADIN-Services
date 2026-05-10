"""Tests für die diagrammübergreifenden Helfer in src.diagrams.graph_queries."""
from __future__ import annotations

from src.diagrams.erd.models import Edge, Graph, Node
from src.diagrams.graph_queries import (
    build_index,
    count_edges_by_kind,
    count_nodes_by_type,
    edge_pair_id,
    find_edge_indexes,
    get_unique_edge,
)


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _node(id_: str, type_: str = "entity") -> Node:
    return Node(id=id_, type=type_)  # type: ignore[arg-type]


def _edge(from_: str, to: str, kind: str | None = None,
          cardinality: tuple[str, str] | None = None) -> Edge:
    payload: dict = {"from": from_, "to": to}
    if kind is not None:
        payload["kind"] = kind
    if cardinality is not None:
        payload["cardinality"] = cardinality
    return Edge(**payload)


# ---------------------------------------------------------------------------
# count_nodes_by_type
# ---------------------------------------------------------------------------

class TestCountNodesByType:
    def test_empty_when_only_one_type(self) -> None:
        graph = Graph(nodes=[_node("E1"), _node("E2")])
        assert count_nodes_by_type(graph) == {"entity": 2}

    def test_counts_each_type(self) -> None:
        graph = Graph(
            nodes=[
                _node("E1", "entity"),
                _node("E2", "entity"),
                _node("R1", "relationship"),
                _node("A1", "attribute"),
            ]
        )
        assert count_nodes_by_type(graph) == {
            "attribute": 1,
            "entity": 2,
            "relationship": 1,
        }

    def test_result_is_sorted_by_key(self) -> None:
        # Sortierung ist Teil des Vertrags — Vergleichsergebnisse sollen
        # deterministisch sein.
        graph = Graph(
            nodes=[
                _node("R1", "relationship"),
                _node("E1", "entity"),
                _node("A1", "attribute"),
            ]
        )
        assert list(count_nodes_by_type(graph).keys()) == [
            "attribute", "entity", "relationship",
        ]


# ---------------------------------------------------------------------------
# count_edges_by_kind
# ---------------------------------------------------------------------------

class TestCountEdgesByKind:
    def test_no_edges_returns_empty_dict(self) -> None:
        graph = Graph(nodes=[_node("E1")])
        assert count_edges_by_kind(graph) == {}

    def test_counts_known_kinds(self) -> None:
        graph = Graph(
            nodes=[_node("E1"), _node("R1", "relationship"),
                   _node("A1", "attribute")],
            edges=[
                _edge("E1", "R1", kind="participates", cardinality=("1", "n")),
                _edge("E1", "A1", kind="hasAttribute"),
                _edge("R1", "A1", kind="hasAttribute"),
            ],
        )
        assert count_edges_by_kind(graph) == {
            "hasAttribute": 2,
            "participates": 1,
        }

    def test_edges_without_kind_become_unknown(self) -> None:
        # kind ist optional; fehlende Werte landen unter "UNKNOWN".
        graph = Graph(
            nodes=[_node("E1"), _node("E2")],
            edges=[_edge("E1", "E2")],
        )
        assert count_edges_by_kind(graph) == {"UNKNOWN": 1}


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    def test_empty_input_returns_empty_dict(self) -> None:
        assert build_index([]) == {}

    def test_indexes_by_node_id(self) -> None:
        nodes = [_node("E1"), _node("E2"), _node("R1", "relationship")]
        index = build_index(nodes)
        assert set(index.keys()) == {"E1", "E2", "R1"}
        assert index["R1"].type == "relationship"


# ---------------------------------------------------------------------------
# edge_pair_id
# ---------------------------------------------------------------------------

class TestEdgePairId:
    def test_format_is_from_arrow_to(self) -> None:
        assert edge_pair_id(_edge("E1", "E2")) == "E1->E2"

    def test_direction_matters(self) -> None:
        # E1->E2 und E2->E1 sind unterschiedliche IDs (Kanten sind gerichtet).
        assert edge_pair_id(_edge("E1", "E2")) != edge_pair_id(_edge("E2", "E1"))


# ---------------------------------------------------------------------------
# find_edge_indexes
# ---------------------------------------------------------------------------

class TestFindEdgeIndexes:
    def test_returns_empty_list_when_no_match(self) -> None:
        edges = [_edge("E1", "E2")]
        assert find_edge_indexes(edges, "E3->E4") == []

    def test_returns_single_index(self) -> None:
        edges = [_edge("E1", "E2"), _edge("E3", "E4")]
        assert find_edge_indexes(edges, "E3->E4") == [1]

    def test_returns_all_matching_indexes(self) -> None:
        # Doppelkanten sind im Schema nicht verboten — Helfer muss sie finden.
        edges = [
            _edge("E1", "E2"),
            _edge("E1", "E2"),
            _edge("E3", "E4"),
            _edge("E1", "E2"),
        ]
        assert find_edge_indexes(edges, "E1->E2") == [0, 1, 3]


# ---------------------------------------------------------------------------
# get_unique_edge
# ---------------------------------------------------------------------------

class TestGetUniqueEdge:
    def test_returns_none_when_no_match(self) -> None:
        assert get_unique_edge([_edge("E1", "E2")], "E3->E4") is None

    def test_returns_index_and_edge_for_unique_match(self) -> None:
        edges = [_edge("E1", "E2"), _edge("E3", "E4")]
        result = get_unique_edge(edges, "E3->E4")
        assert result is not None
        idx, edge = result
        assert idx == 1
        assert edge.from_ == "E3"
        assert edge.to == "E4"

    def test_returns_none_when_multiple_match(self) -> None:
        # Mehrdeutigkeit wird absichtlich nicht aufgelöst — Aufrufer entscheidet.
        edges = [_edge("E1", "E2"), _edge("E1", "E2")]
        assert get_unique_edge(edges, "E1->E2") is None
