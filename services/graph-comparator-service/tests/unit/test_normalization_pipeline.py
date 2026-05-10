"""Tests für DefaultNormalizationPipeline.

Die echten Steps (FlagsNormalizer, LabelsNormalizer, CardinalityNormalizer)
sind aktuell nicht implementiert (NotImplementedError). Hier wird nur die
Pipeline-Mechanik getestet — Reihenfolge, Pass-Through, Verkettung.
"""
from __future__ import annotations

from src.diagrams.erd.models import Graph, Node
from src.normalization.base import Normalizer
from src.normalization.default_pipeline import DefaultNormalizationPipeline


def _graph(node_ids: list[str]) -> Graph:
    return Graph(nodes=[Node(id=i, type="entity") for i in node_ids])


class _IdentityNormalizer(Normalizer):
    """Pass-Through, zählt nur seine Aufrufe."""

    def __init__(self) -> None:
        self.calls = 0

    def normalize(self, graph: Graph) -> Graph:
        self.calls += 1
        return graph


class _RenameToFooNormalizer(Normalizer):
    """Setzt label aller Knoten auf 'foo' — sichtbarer Effekt zum Testen."""

    def normalize(self, graph: Graph) -> Graph:
        return graph.model_copy(
            update={"nodes": [n.model_copy(update={"label": "foo"})
                              for n in graph.nodes]}
        )


class _AppendLabelNormalizer(Normalizer):
    """Hängt einen Suffix an alle Labels — zeigt, dass Reihenfolge zählt."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def normalize(self, graph: Graph) -> Graph:
        return graph.model_copy(
            update={"nodes": [n.model_copy(update={"label": n.label + self.suffix})
                              for n in graph.nodes]}
        )


class TestDefaultNormalizationPipeline:
    def test_empty_pipeline_passes_graph_through(self) -> None:
        graph = _graph(["E1"])
        result = DefaultNormalizationPipeline(steps=[]).run(graph)
        assert result == graph

    def test_each_step_is_called_once(self) -> None:
        a = _IdentityNormalizer()
        b = _IdentityNormalizer()
        DefaultNormalizationPipeline(steps=[a, b]).run(_graph(["E1"]))
        assert a.calls == 1
        assert b.calls == 1

    def test_step_output_becomes_input_of_next_step(self) -> None:
        # Erst Labels auf 'foo' setzen, dann '_x' anhängen → erwartet 'foo_x'.
        pipeline = DefaultNormalizationPipeline(steps=[
            _RenameToFooNormalizer(),
            _AppendLabelNormalizer("_x"),
        ])
        result = pipeline.run(_graph(["E1", "E2"]))
        assert all(n.label == "foo_x" for n in result.nodes)

    def test_step_order_matters(self) -> None:
        # Umgekehrte Reihenfolge → 'foo' (anhängen vor rename ist wirkungslos).
        pipeline = DefaultNormalizationPipeline(steps=[
            _AppendLabelNormalizer("_x"),
            _RenameToFooNormalizer(),
        ])
        result = pipeline.run(_graph(["E1"]))
        assert all(n.label == "foo" for n in result.nodes)
