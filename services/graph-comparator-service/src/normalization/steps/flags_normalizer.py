"""
Flags sortieren und deduplizieren.
Flags sind konzeptionell eine Menge (Reihenfolge egal), werden aber im JSON als Liste repräsentiert.
Hier: sortieren + Duplikate entfernen.
"""
from __future__ import annotations

from src.diagrams.erd.models import Graph
from src.normalization.base import Normalizer


class FlagsNormalizer(Normalizer):
    def normalize(self, graph: Graph) -> Graph:
        raise NotImplementedError
