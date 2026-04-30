"""Standard-Normalisierungspipeline: führt Schritte sequentiell aus."""
from __future__ import annotations

from src.diagrams.erd.models import Graph
from src.normalization.base import NormalizationPipeline, Normalizer


class DefaultNormalizationPipeline(NormalizationPipeline):
    """Sequentielle Pipeline.

    Die Reihenfolge der Schritte ist bedeutungstragend: z.B. sollten
    Flags sortiert werden, bevor kanonisiert wird.
    """

    def __init__(self, steps: list[Normalizer]) -> None:
        self.steps = steps

    def run(self, graph: Graph) -> Graph:
        for step in self.steps:
            graph = step.normalize(graph)
        return graph
