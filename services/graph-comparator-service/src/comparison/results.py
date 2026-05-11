"""
Ergebnistypen für den Vergleich.
Pydantic-Modelle, damit FastAPI automatisch zu JSON serialisieren kann.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DiffOpType = Literal[
    "node_missing",   # in reference aber nicht in candidate
    "node_extra",     # in candidate aber nicht in reference
    "node_modified",  # beide vorhanden, Eigenschaften abweichend
    "edge_missing",
    "edge_extra",
    "edge_modified",
]

Severity = Literal["error", "warning", "info"]



class DiffOperation(BaseModel):
    """
    Eine einzelne Abweichung zwischen reference und candidate (nach erd-diff.v1-Schema).
    Wird in ComparisonResult.differences gesammelt.
    """
    model_config = ConfigDict(extra="forbid")

    op: DiffOpType
    target: str
    severity: Severity = "error"
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    # TODO: ggf. category für kumulierte Fehler (z.B. "Übermodellierung")



# Pydantic-Modell-Klassen für die Vergleichsergebnisse
class ComparisonResult(BaseModel):
    """Vollständiges Vergleichsergebnis."""

    # akzeptiere nur definierte Felder:
    model_config = ConfigDict(extra="forbid")

    #
    # Pflichtfelder
    #

    # Stimmt mit Musterlösung überein oder nicht?
    match: bool


    #
    # Automatisch generierte Felder aus dem Vergleichsprozess
    #

    # Alle Abweichungen, die gefunden wurden (leere Liste = keine Abweichungen)
    differences: list[DiffOperation] = Field(default_factory=list)
    
    # Feedback-Texte für den Nutzer
    feedback: list[str] = Field(default_factory=list)
    
    # Statistiken
    stats: dict[str, Any] = Field(default_factory=dict)


    #
    # Optionale Felder für erweiterte Informationen
    # (optional = Defaultwert angegeben)
    #

    # Wie sicher ist sich das System beim Vergleich? (Standard 1.0 = volle Sicherheit, 0.0 = keine Aussage möglich)
    confidence: float = 1.0

    warnings: list[str] = Field(default_factory=list)

    # ggf. Version der Vergleichspipeline, damit Feedback auf bekannte Fehler oder Einschränkungen bezogen werden kann
    pipeline_version: str | None = None