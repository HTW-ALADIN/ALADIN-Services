# diagrams/erd/

Entity-Relationship-Diagramm nach `erd.v1`-Schema.

## Knotentypen

- `entity` - Entitätstyp (z.B. "Student")
- `relationship` - Beziehungstyp (z.B. "besucht")
- `attribute` - Attribut (z.B. "Name"), gehört über hasAttribute-Edge zu Owner
- `isa` - ISA-Knoten für Generalisierung/Spezialisierung

## Kantentypen

- `participates` - Entity nimmt an Relationship teil (mit Kardinalität)
- `hasAttribute` - Owner (entity/relationship) hat Attribut
- `isaSuper` - ISA-Knoten zeigt auf Supertyp
- `isaSub` - ISA-Knoten zeigt auf Subtyp

## Dateien

- `models.py` - Pydantic-Modelle `Node`, `Edge`, `Graph`.
- `ops.py` - ERD-spezifische Graph-Operationen (Owner-Auflösung, ISA-Hierarchie-Extraktion).

## Schema-Referenz

Siehe `erd_v1_schema.json`
