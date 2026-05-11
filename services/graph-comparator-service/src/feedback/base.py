"""Interface für Feedback-Erzeugung.

FeedbackBuilder vergleichen nicht selbst. Sie formulieren nur Ergebnisse um.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.comparison.results import ComparisonResult


class FeedbackBuilder(ABC):
    """Basisklasse für Feedback-Erzeuger."""

    @abstractmethod
    def build(self, result: ComparisonResult) -> list[str]:
        """Erzeugt Feedback-Texte aus einem Vergleichsergebnis."""
        raise NotImplementedError