"""Interfaces für Normalisierungs-Schritte und -Pipelines."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.diagrams.erd.models import Graph


class Normalizer(ABC):
    """
    Ein einzelner Normalisierungsschritt.
    Nimmt einen Graph entgegen und gibt einen transformierten Graph zurück.
    Implementierungen sollen idempotent sein.
    """

    @abstractmethod
    def normalize(self, graph: Graph) -> Graph:
        ...


class NormalizationPipeline(ABC):
    """Führt eine Folge von Normalizern/Normalisierungsschritten aus."""

    @abstractmethod
    def run(self, graph: Graph) -> Graph:
        ...
