"""Tests für DefaultFeedbackBuilder."""
from __future__ import annotations

from src.comparison.results import ComparisonResult
from src.feedback.default_feedback_builder import DefaultFeedbackBuilder


def _result(match: bool, ref_nodes: dict | None = None,
            cand_nodes: dict | None = None,
            ref_edges: dict | None = None,
            cand_edges: dict | None = None) -> ComparisonResult:
    """Baut ein ComparisonResult mit den minimal nötigen stats für den Builder."""
    return ComparisonResult(
        match=match,
        stats={
            "reference": {
                "nodes_by_type": ref_nodes or {},
                "edges_by_kind": ref_edges or {},
            },
            "candidate": {
                "nodes_by_type": cand_nodes or {},
                "edges_by_kind": cand_edges or {},
            },
        },
    )


class TestDefaultFeedbackBuilder:
    def test_match_returns_single_positive_message(self) -> None:
        result = _result(match=True)
        feedback = DefaultFeedbackBuilder().build(result)
        assert len(feedback) == 1
        assert "übereinstimmen" not in feedback[0].lower() or "stimmt" in feedback[0]

    def test_node_mismatch_includes_both_counts(self) -> None:
        result = _result(
            match=False,
            ref_nodes={"entity": 2},
            cand_nodes={"entity": 1},
        )
        feedback = DefaultFeedbackBuilder().build(result)
        # Es muss erkennbar sein, was Soll und was Ist ist.
        joined = " ".join(feedback)
        assert "Knoten" in joined
        assert "Musterlösung" in joined
        assert "Deine Lösung" in joined

    def test_edge_mismatch_is_reported(self) -> None:
        result = _result(
            match=False,
            ref_edges={"participates": 2},
            cand_edges={"participates": 1},
        )
        feedback = DefaultFeedbackBuilder().build(result)
        assert any("Kanten" in line for line in feedback)

    def test_node_match_but_edge_mismatch_only_reports_edges(self) -> None:
        # Nur Kanten weichen ab — Knoten-Feedback wäre verwirrend.
        result = _result(
            match=False,
            ref_nodes={"entity": 1},
            cand_nodes={"entity": 1},
            ref_edges={"participates": 1},
            cand_edges={},
        )
        feedback = DefaultFeedbackBuilder().build(result)
        assert any("Kanten" in line for line in feedback)
        assert not any("Knoten" in line for line in feedback)

    def test_no_stats_falls_back_to_generic_message(self) -> None:
        # Wenn der Comparator keine Stats geliefert hat, muss der Builder
        # trotzdem etwas Sinnvolles zurückgeben statt zu crashen.
        result = ComparisonResult(match=False)
        feedback = DefaultFeedbackBuilder().build(result)
        assert len(feedback) >= 1
