"""Tests für die Pydantic-Modelle in src.diagrams.erd.models.

Geprüft werden Validatoren und Schema-Constraints, NICHT, ob Pydantic
selbst funktioniert.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.diagrams.erd.models import Edge, Graph, Node


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class TestNode:
    def test_minimal_entity_is_valid(self) -> None:
        node = Node(id="E1", type="entity")
        assert node.id == "E1"
        assert node.type == "entity"
        assert node.flags == []
        assert node.key is None

    def test_attribute_with_key_is_valid(self) -> None:
        node = Node(id="A1", type="attribute", key="PK")
        assert node.key == "PK"

    def test_key_on_non_attribute_is_rejected(self) -> None:
        # 'key' ist nur bei type=attribute erlaubt.
        with pytest.raises(ValidationError, match="key"):
            Node(id="E1", type="entity", key="PK")

    def test_flags_duplicates_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplikate"):
            Node(id="E1", type="entity", flags=["weak", "weak"])

    def test_flags_unique_is_valid(self) -> None:
        node = Node(id="E1", type="entity", flags=["weak", "abstract"])
        assert node.flags == ["weak", "abstract"]

    def test_unknown_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Node(id="X", type="something-else")  # type: ignore[arg-type]

    def test_extra_field_is_rejected(self) -> None:
        # extra="forbid" — sonst können Tippfehler unbemerkt durchrutschen.
        with pytest.raises(ValidationError):
            Node(id="E1", type="entity", extra_field="x")  # type: ignore[call-arg]

    def test_empty_id_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Node(id="", type="entity")

    def test_id_with_invalid_characters_is_rejected(self) -> None:
        # Pattern erlaubt nur [A-Za-z0-9_\-:.]
        with pytest.raises(ValidationError):
            Node(id="E 1", type="entity")


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class TestEdge:
    def test_participates_requires_cardinality(self) -> None:
        with pytest.raises(ValidationError, match="cardinality"):
            Edge(**{"from": "E1", "to": "R1", "kind": "participates"})

    def test_participates_with_cardinality_is_valid(self) -> None:
        edge = Edge(
            **{"from": "E1", "to": "R1", "kind": "participates",
               "cardinality": ("1", "n")}
        )
        assert edge.cardinality == ("1", "n")

    @pytest.mark.parametrize("kind", ["hasAttribute", "isaSuper", "isaSub"])
    def test_non_participates_with_cardinality_is_rejected(self, kind: str) -> None:
        with pytest.raises(ValidationError, match="darf keine 'cardinality'"):
            Edge(
                **{"from": "E1", "to": "A1", "kind": kind,
                   "cardinality": ("1", "n")}
            )

    @pytest.mark.parametrize("kind", ["hasAttribute", "isaSuper", "isaSub"])
    def test_non_participates_without_cardinality_is_valid(self, kind: str) -> None:
        edge = Edge(**{"from": "E1", "to": "A1", "kind": kind})
        assert edge.cardinality is None

    def test_from_alias_is_used_when_loading(self) -> None:
        # JSON-Eingabe nutzt "from", Modellfeld heißt from_.
        edge = Edge.model_validate({"from": "E1", "to": "E2"})
        assert edge.from_ == "E1"

    def test_dump_with_by_alias_produces_from_key(self) -> None:
        # Roundtrip: ein nach JSON serialisiertes Modell muss wieder
        # mit Pydantic geladen werden können.
        edge = Edge(**{"from": "E1", "to": "E2"})
        dumped = edge.model_dump(by_alias=True, mode="json")
        assert "from" in dumped
        assert "from_" not in dumped


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def _entity(id_: str) -> Node:
    return Node(id=id_, type="entity")


class TestGraph:
    def test_minimal_graph_is_valid(self) -> None:
        graph = Graph(nodes=[_entity("E1")])
        assert len(graph.nodes) == 1
        assert graph.edges == []

    def test_empty_nodes_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Graph(nodes=[])

    def test_duplicate_node_ids_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Doppelte Knoten-ID"):
            Graph(nodes=[_entity("E1"), _entity("E1")])

    def test_edge_from_must_reference_existing_node(self) -> None:
        with pytest.raises(ValidationError, match="'from' verweist"):
            Graph(
                nodes=[_entity("E1")],
                edges=[Edge(**{"from": "GHOST", "to": "E1"})],
            )

    def test_edge_to_must_reference_existing_node(self) -> None:
        with pytest.raises(ValidationError, match="'to' verweist"):
            Graph(
                nodes=[_entity("E1")],
                edges=[Edge(**{"from": "E1", "to": "GHOST"})],
            )

    def test_schema_field_accepts_erd_v1(self) -> None:
        graph = Graph.model_validate(
            {"schema": "erd.v1", "nodes": [{"id": "E1", "type": "entity"}]}
        )
        assert graph.schema_ == "erd.v1"

    def test_schema_field_rejects_other_versions(self) -> None:
        with pytest.raises(ValidationError):
            Graph.model_validate(
                {"schema": "erd.v2", "nodes": [{"id": "E1", "type": "entity"}]}
            )

    def test_full_roundtrip_with_aliases(self) -> None:
        # Der Roundtrip ist die wichtigste Garantie: was reinkommt, kann auch
        # wieder serialisiert und neu eingelesen werden.
        payload = {
            "schema": "erd.v1",
            "nodes": [
                {"id": "E1", "type": "entity"},
                {"id": "E2", "type": "entity"},
            ],
            "edges": [{"from": "E1", "to": "E2"}],
        }
        graph = Graph.model_validate(payload)
        dumped = graph.model_dump(by_alias=True, mode="json", exclude_none=True)
        reloaded = Graph.model_validate(dumped)
        assert reloaded == graph
