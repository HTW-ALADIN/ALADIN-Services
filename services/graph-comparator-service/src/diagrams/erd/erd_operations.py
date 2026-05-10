"""ERD-spezifische Graph-Operationen.

Diese Operationen nutzen Wissen über die ERD-Semantik (z.B. dass
Attribute über hasAttribute-Kanten zu Ownern gehören, oder dass
ISA-Knoten über isaSuper/isaSub-Kanten mit Entities verbunden sind).

Im Gegensatz zu ``diagrams/graph_ops.py`` sind diese Funktionen nicht
wiederverwendbar für andere Diagrammtypen.
"""
from __future__ import annotations

from src.diagrams.erd.models import Graph


def find_owners(graph: Graph) -> dict[str, str]:
    """Ermittelt für jedes Attribut den Owner (Entity/Relationship).

    Folgt den hasAttribute-Kanten und bestimmt, welche Seite das Attribut
    ist und welche der Owner (Richtung in den Daten nicht garantiert).

    Rückgabe: ``{attribut_id: owner_id}``.
    """
    raise NotImplementedError


def isa_hierarchy(graph: Graph) -> dict[str, tuple[str, frozenset[str]]]:
    """Extrahiert für jeden ISA-Knoten seine Hierarchie.

    Rückgabe: ``{isa_id: (super_label, frozenset(sub_labels))}``.

    TODO: Reihenfolge ist kritisch. ISA-Knoten haben oft generische Labels
    ("isa1"), ihre Identität ergibt sich aus Super + Subs. Matching muss
    also nach den verknüpften Entities passieren, nicht davor.
    """
    raise NotImplementedError
