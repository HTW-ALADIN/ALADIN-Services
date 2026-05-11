from __future__ import annotations

from src.comparison.base import GraphComparator
from src.comparison.results import ComparisonResult
from src.diagrams.erd.models import Graph
from src.diagrams.graph_queries import count_edges_by_kind, count_nodes_by_type


class DefaultComparator(GraphComparator):
    """Einfacher Comparator: vergleicht nur Zählwerte."""

    def compare(self, reference: Graph, candidate: Graph) -> ComparisonResult:
        reference_stats = {
            "nodes_by_type": count_nodes_by_type(reference),
            "edges_by_kind": count_edges_by_kind(reference),
        }
        candidate_stats = {
            "nodes_by_type": count_nodes_by_type(candidate),
            "edges_by_kind": count_edges_by_kind(candidate),
        }

        match = reference_stats == candidate_stats

        return ComparisonResult(
            match=match,
            differences=[],
            stats={
                "reference": reference_stats,
                "candidate": candidate_stats,
            },
            confidence=1.0,
            warnings=[
                "Aktuell werden nur die Anzahlen von Knotentypen und Kantenarten verglichen."
            ],
            pipeline_version="counts.v1",
        )