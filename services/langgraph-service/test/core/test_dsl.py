"""Unit tests for the graph definition DSL."""

import pytest
from pydantic import ValidationError

from core.dsl import GraphDefinition, lookup_path
from core.errors import DSLValidationError


def _transform_graph(**overrides):
    payload = {
        "name": "t",
        "nodes": [
            {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]},
            {"id": "b", "type": "transform", "operations": [{"op": "pick", "from_key": "value"}]},
        ],
        "edges": [["a", "b"]],
        "entry": "a",
    }
    payload.update(overrides)
    return payload


def test_valid_transform_graph():
    definition = GraphDefinition.model_validate(_transform_graph())
    assert definition.entry == "a"
    assert len(definition.nodes) == 2


def test_duplicate_node_ids_rejected():
    payload = _transform_graph()
    payload["nodes"][1]["id"] = "a"
    with pytest.raises(ValidationError, match="unique"):
        GraphDefinition.model_validate(payload)


def test_unknown_entry_rejected():
    with pytest.raises(ValidationError, match="entry"):
        GraphDefinition.model_validate(_transform_graph(entry="missing"))


def test_entry_must_not_be_conditional():
    payload = {
        "name": "c",
        "nodes": [
            {"id": "branch", "type": "conditional", "cases": [], "default_goto": "a"},
            {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]},
        ],
        "edges": [],
        "conditional_edges": [],
        "entry": "branch",
    }
    with pytest.raises(Exception):  # noqa: B017, PT011
        GraphDefinition.model_validate(payload)


def test_dangling_edge_rejected():
    with pytest.raises(ValidationError, match="not a defined node"):
        GraphDefinition.model_validate(_transform_graph(edges=[["a", "ghost"]]))


def test_conditional_must_use_conditional_edges():
    payload = _transform_graph()
    payload["nodes"].append(
        {
            "id": "branch",
            "type": "conditional",
            "cases": [{"key": "value", "equals": 1, "goto": "b"}],
            "default_goto": "b",
        }
    )
    payload["edges"] = [["a", "b"], ["b", "branch"]]
    with pytest.raises(ValidationError, match="conditional_edges"):
        GraphDefinition.model_validate(payload)


def test_conditional_unknown_goto_rejected():
    payload = {
        "name": "c",
        "nodes": [
            {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]},
            {
                "id": "branch",
                "type": "conditional",
                "cases": [{"key": "value", "equals": 1, "goto": "ghost"}],
                "default_goto": "a",
            },
        ],
        "edges": [],
        "conditional_edges": [{"source": "a", "node": "branch"}],
        "entry": "a",
    }
    with pytest.raises(ValidationError, match="unknown node"):
        GraphDefinition.model_validate(payload)


def test_http_forbidden_headers_rejected():
    payload = {
        "name": "h",
        "nodes": [
            {
                "id": "call",
                "type": "http",
                "url": "https://example.com/api",
                "headers": {"Authorization": "Bearer x"},
                "output_key": "out",
            }
        ],
        "edges": [],
        "entry": "call",
    }
    with pytest.raises(Exception, match="not allowed"):  # noqa: PT011
        GraphDefinition.model_validate(payload)


def test_http_non_json_content_type_rejected():
    payload = {
        "name": "h",
        "nodes": [
            {
                "id": "call",
                "type": "http",
                "url": "https://example.com/api",
                "headers": {"Content-Type": "text/plain"},
                "output_key": "out",
            }
        ],
        "edges": [],
        "entry": "call",
    }
    with pytest.raises(Exception, match="application/json"):  # noqa: PT011
        GraphDefinition.model_validate(payload)


def test_llm_requires_prompt_source():
    payload = {
        "name": "l",
        "nodes": [
            {"id": "gen", "type": "llm", "provider": "openai", "model": "gpt-4o", "output_key": "t"}
        ],
        "edges": [],
        "entry": "gen",
    }
    with pytest.raises(Exception, match="input_key or prompt_template"):  # noqa: PT011
        GraphDefinition.model_validate(payload)


def test_lookup_path_basics():
    state = {"a": {"b": [{"c": 42}]}}
    assert lookup_path(state, "$.a.b.0.c") == 42
    with pytest.raises(DSLValidationError):
        lookup_path(state, "$.a.missing")
    with pytest.raises(DSLValidationError):
        lookup_path(state, "a.b")
    with pytest.raises(DSLValidationError):
        lookup_path({"a": [1]}, "$.a.x")
    with pytest.raises(DSLValidationError):
        lookup_path({"a": 1}, "$.a.b")
