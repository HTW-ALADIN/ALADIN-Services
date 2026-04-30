"""Standard-FeedbackBuilder für den rudimentären Count-Vergleich."""

from __future__ import annotations

from src.feedback.base import FeedbackBuilder
from src.comparison.results import ComparisonResult


class DefaultFeedbackBuilder(FeedbackBuilder):
    """Formuliert einfaches Feedback aus Count-Statistiken."""

    def build(self, result: ComparisonResult) -> list[str]:
        if result.match:
            return [
                "Die Anzahl der Knoten-Typen und Kanten-Arten stimmt mit der Musterlösung überein."
            ]

        feedback: list[str] = []

        stats = result.stats
        reference = stats.get("reference", {})
        candidate = stats.get("candidate", {})

        ref_nodes = reference.get("nodes_by_type", {})
        cand_nodes = candidate.get("nodes_by_type", {})

        ref_edges = reference.get("edges_by_kind", {})
        cand_edges = candidate.get("edges_by_kind", {})

        if ref_nodes != cand_nodes:
            feedback.append(
                "Die Anzahl der Knoten-Typen weicht von der Musterlösung ab."
            )
            feedback.append(f"Musterlösung Knoten: {ref_nodes}")
            feedback.append(f"Deine Lösung Knoten: {cand_nodes}")

        if ref_edges != cand_edges:
            feedback.append(
                "Die Anzahl der Kanten-Arten weicht von der Musterlösung ab."
            )
            feedback.append(f"Musterlösung Kanten: {ref_edges}")
            feedback.append(f"Deine Lösung Kanten: {cand_edges}")

        if not feedback:
            feedback.append(
                "Es wurde eine Abweichung erkannt, aber noch kein detailliertes Feedback erzeugt."
            )

        return feedback