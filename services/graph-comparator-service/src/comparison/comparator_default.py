from __future__ import annotations

from typing import Any

from src.comparison.results import ComparisonResult
from src.diagrams.graph_queries import count_edges_by_kind, count_nodes_by_type


class DefaultComparator:
    """Einfacher Comparator: vergleicht nur Zählwerte."""

    def compare(self, reference: Any, candidate: Any) -> ComparisonResult:
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
            limitations=[
                "Aktuell werden nur die Anzahlen von Knotentypen und Kantenarten verglichen."
            ],
            pipeline_version="counts.v1",
        )