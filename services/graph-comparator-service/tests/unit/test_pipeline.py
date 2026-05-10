"""End-to-end Tests für run_comparison_pipeline.

Testet das Zusammenspiel der Schritte (validate → normalize → compare → feedback)
und die Fehlerpfade.
"""
from __future__ import annotations

import pytest

from src.main import run_comparison_pipeline


def _entity(id_: str) -> dict:
    return {"id": id_, "type": "entity"}


def _valid_graph_payload(node_ids: list[str]) -> dict:
    return {
        "schema": "erd.v1",
        "nodes": [_entity(i) for i in node_ids],
        "edges": [],
    }


class TestRunComparisonPipeline:
    def test_identical_payloads_match_with_feedback(self) -> None:
        payload = _valid_graph_payload(["E1", "E2"])
        result = run_comparison_pipeline(payload, payload)
        assert result.match is True
        # Feedback wird im letzten Schritt angereichert — darf nicht leer sein.
        assert len(result.feedback) >= 1

    def test_mismatched_payloads_do_not_match(self) -> None:
        ref = _valid_graph_payload(["E1", "E2"])
        cand = _valid_graph_payload(["E1"])
        result = run_comparison_pipeline(ref, cand)
        assert result.match is False
        assert len(result.feedback) >= 1

    def test_invalid_reference_returns_validation_failure(self) -> None:
        # Pflichtfeld 'type' fehlt — pydantic.ValidationError soll
        # in ein ComparisonResult mit match=False umgewandelt werden,
        # NICHT zu einer 500er-Exception eskalieren.
        invalid = {"nodes": [{"id": "E1"}]}
        valid = _valid_graph_payload(["E1"])
        result = run_comparison_pipeline(invalid, valid)
        assert result.match is False
        assert any("Format" in line or "ungültig" in line.lower()
                   for line in result.feedback)
        assert any("ungültiger Eingabedaten" in w for w in result.warnings)

    def test_invalid_candidate_returns_validation_failure(self) -> None:
        valid = _valid_graph_payload(["E1"])
        invalid = {"nodes": [{"id": "E1", "type": "not-a-real-type"}]}
        result = run_comparison_pipeline(valid, invalid)
        assert result.match is False

    def test_empty_nodes_in_payload_is_validation_failure(self) -> None:
        # Graph erfordert mindestens einen Knoten.
        payload = {"nodes": []}
        result = run_comparison_pipeline(payload, payload)
        assert result.match is False

    def test_unexpected_exception_is_propagated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Andere Exceptions als ValidationError sollen NICHT gefangen werden,
        # damit FastAPI sie als 500 ausliefert. Wir simulieren einen Bug im
        # Compare-Schritt, indem wir compare_graphs durch eine fehlerhafte
        # Variante ersetzen.
        from src import main

        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated bug")

        monkeypatch.setattr(main, "compare_graphs", boom)

        with pytest.raises(RuntimeError, match="simulated bug"):
            run_comparison_pipeline(
                _valid_graph_payload(["E1"]),
                _valid_graph_payload(["E1"]),
            )
