"""Tests für DefaultComparator (count-basierter Vergleich)."""
from __future__ import annotations

from src.comparison.default_comparator import DefaultComparator
from src.diagrams.erd.models import Edge, Graph, Node


def _node(id_: str, type_: str = "entity") -> Node:
    return Node(id=id_, type=type_)  # type: ignore[arg-type]


def _participates(from_: str, to: str) -> Edge:
    return Edge(**{"from": from_, "to": to, "kind": "participates",
                   "cardinality": ("1", "n")})


class TestDefaultComparator:
    def test_identical_graphs_match(self) -> None:
        graph = Graph(
            nodes=[_node("E1"), _node("R1", "relationship")],
            edges=[_participates("E1", "R1")],
        )
        # Wir vergleichen denselben Graph mit sich selbst — muss matchen.
        result = DefaultComparator().compare(graph, graph)
        assert result.match is True
        assert result.differences == []
        assert result.pipeline_version == "counts.v1"

    def test_warning_is_present_about_count_only(self) -> None:
        # DefaultComparator muss den Nutzer darauf hinweisen, dass nur
        # Counts verglichen werden — sonst wird "match=True" überinterpretiert.
        graph = Graph(nodes=[_node("E1")])
        result = DefaultComparator().compare(graph, graph)
        assert any("Anzahl" in w for w in result.warnings)

    def test_different_node_counts_do_not_match(self) -> None:
        ref = Graph(nodes=[_node("E1"), _node("E2")])
        cand = Graph(nodes=[_node("E1")])
        result = DefaultComparator().compare(ref, cand)
        assert result.match is False

    def test_different_edge_kinds_do_not_match(self) -> None:
        ref = Graph(
            nodes=[_node("E1"), _node("R1", "relationship")],
            edges=[_participates("E1", "R1")],
        )
        cand = Graph(
            nodes=[_node("E1"), _node("R1", "relationship")],
            edges=[],
        )
        result = DefaultComparator().compare(ref, cand)
        assert result.match is False

    def test_stats_contain_reference_and_candidate(self) -> None:
        ref = Graph(nodes=[_node("E1"), _node("E2")])
        cand = Graph(nodes=[_node("E1")])
        result = DefaultComparator().compare(ref, cand)
        assert "reference" in result.stats
        assert "candidate" in result.stats
        assert result.stats["reference"]["nodes_by_type"] == {"entity": 2}
        assert result.stats["candidate"]["nodes_by_type"] == {"entity": 1}

    def test_match_is_independent_of_node_order(self) -> None:
        # Counts sind reihenfolgeunabhängig — Reihenfolge der Knoten
        # darf das Ergebnis nicht ändern.
        ref = Graph(nodes=[_node("E1"), _node("R1", "relationship")])
        cand = Graph(nodes=[_node("R2", "relationship"), _node("E2")])
        result = DefaultComparator().compare(ref, cand)
        assert result.match is True
