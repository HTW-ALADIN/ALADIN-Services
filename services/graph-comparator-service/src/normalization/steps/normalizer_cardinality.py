"""
Kardinalitäten vereinheitlichen.
m, n, * bedeuten dasselbe (beliebige Anzahl), wird hier als many kanonisiert.
"""
from __future__ import annotations

from src.diagrams.erd.models import Graph
from src.normalization.base import Normalizer


class CardinalityNormalizer(Normalizer):
    """Vereinheitlicht Kardinalitätsnotation auf Kanten vom Typ ``participates``."""

    MAPPING: dict[str, str] = {"m": "many", "n": "many", "*": "many"}

    def normalize(self, graph: Graph) -> Graph:
        raise NotImplementedError
