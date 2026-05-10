"""
Label-Normalisierung:
trim, lowercase, optional relaxed (ohne Trenner).
"""
from __future__ import annotations

from src.diagrams.erd.models import Graph
from src.normalization.base import Normalizer


class LabelsNormalizer(Normalizer):
    """Normalisiert Labels von Nodes.

    Parameter:
        strip: Whitespace am Rand entfernen.
        lower: Labels auf lowercase bringen.
        relaxed: Zusätzlich Bindestriche/Unterstriche/Punkte/Spaces entfernen.
    """

    def __init__(
        self,
        strip: bool = True,
        lower: bool = True,
        relaxed: bool = False,
    ) -> None:
        self.strip = strip
        self.lower = lower
        self.relaxed = relaxed

    def normalize(self, graph: Graph) -> Graph:
        raise NotImplementedError
