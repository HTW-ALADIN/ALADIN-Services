"""Interface für alle Vergleichs-Implementierungen."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.comparison.results import ComparisonResult
from src.diagrams.erd.models import Graph


class GraphComparator(ABC):

    @abstractmethod
    def compare(
        self, reference: Graph, candidate: Graph
    ) -> ComparisonResult:
        ...
