"""Pydantic-Modelle für ERD-Diagramme gemäß erd.v1-JSON-Schema.

Validierung (Feldtypen, Enums, Pflichtfelder, Referenzintegrität) passiert beim
Instanziieren automatisch und entspricht dem erd.v1-JSON-Schema.

Typisches Laden aus JSON::

    graph = Graph.model_validate_json(path.read_text(encoding="utf-8"))

Serialisieren zurück:

    data = graph.model_dump(by_alias=True, mode="json")
    json.dumps(data, ensure_ascii=False)

by_alias=True ist wichtig, damit from_ wieder zu "from" wird
und schema_ zu "schema".

http://docs.pydantic.dev
"""

from __future__ import annotations
from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Enums / Literals entsprechend dem JSON-Schema
# ---------------------------------------------------------------------------

NodeType = Literal["entity", "relationship", "attribute", "isa"]
AttributeKey = Literal["NONE", "PK", "PARTIAL"]
EdgeKind = Literal["participates", "hasAttribute", "isaSuper", "isaSub"]
CardinalityValue = Literal["", "0..1", "1", "n", "m", "*", "0..n", "1..n"]

# IDs: alphanumerisch plus _ - : .
ID_PATTERN = r"^[A-Za-z0-9_\-:.]+$"
IdString = Annotated[str, Field(pattern=ID_PATTERN, min_length=1)]


# ---------------------------------------------------------------------------
# Knoten
# ---------------------------------------------------------------------------

class Node(BaseModel):
    """Ein Knoten im ERD."""

    # verbietet Felder, die nicht im  Schema definiert sind
    model_config = ConfigDict(extra="forbid")

    id: IdString
    type: NodeType
    label: str = ""
    flags: list[str] = Field(default_factory=list)
    key: AttributeKey | None = None

    # flags muss duplikatfrei sein.
    @field_validator("flags")
    @classmethod
    def _flags_unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("flags enthält Duplikate")
        return v

    # key ist nur bei type="attribute" erlaubt.
    @model_validator(mode="after")
    def _key_only_on_attributes(self) -> "Node":
        if self.key is not None and self.type != "attribute":
            raise ValueError(
                f"Feld 'key' ist nur bei type='attribute' erlaubt, "
                f"nicht bei type={self.type!r} (Knoten {self.id!r})"
            )
        return self


# ---------------------------------------------------------------------------
# Kanten
# ---------------------------------------------------------------------------

class Edge(BaseModel):
    """Eine Kante im ERD."""

    """
    Feldname ist from_ (mit Unterstrich), weil from ein reserviertes
    Python-Keyword ist. Per Alias wird im JSON "from" gelesen und
    geschrieben - beim Serialisieren also immer by_alias=True benutzen.
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: IdString = Field(alias="from")
    to: IdString
    kind: EdgeKind | None = None
    cardinality: tuple[CardinalityValue, CardinalityValue] | None = None

    # participates-Kanten müssen cardinality haben
    # hasAttribute, isaSuper, isaSub dürfen keine cardinality haben.
    @model_validator(mode="after")
    def _cardinality_matches_kind(self) -> "Edge":
        if self.kind == "participates" and self.cardinality is None:
            raise ValueError(
                "Kante vom Typ 'participates' benötigt 'cardinality' "
                f"({self.from_}->{self.to})"
            )
        if (
            self.kind in ("hasAttribute", "isaSuper", "isaSub")
            and self.cardinality is not None
        ):
            raise ValueError(
                f"Kante vom Typ {self.kind!r} darf keine 'cardinality' haben "
                f"({self.from_}->{self.to})"
            )
        return self


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class Graph(BaseModel):
    """Komplettes ER-Diagramm."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # das optionale schema-Feld soll, falls gesetzt, "erd.v1" sein.
    schema_: Literal["erd.v1"] | None = Field(default=None, alias="schema")
    
    # es muss mindestens einen Knoten geben, damit das Diagramm Sinn ergibt.
    nodes: list[Node] = Field(min_length=1)

    # edges können leer sein, da z.B. ein einzelner Entity-Knoten ohne Beziehungen erlaubt ist.
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids_and_valid_refs(self) -> "Graph":
        seen: set[str] = set()
        for n in self.nodes:
            if n.id in seen:
                raise ValueError(f"Doppelte Knoten-ID: {n.id!r}")
            seen.add(n.id)

        # from-to der Kanten müssen auf existierende Knoten verweisen.
        for i, e in enumerate(self.edges):
            if e.from_ not in seen:
                raise ValueError(
                    f"edges[{i}]: 'from' verweist auf unbekannte ID {e.from_!r}"
                )
            if e.to not in seen:
                raise ValueError(
                    f"edges[{i}]: 'to' verweist auf unbekannte ID {e.to!r}"
                )
        return self