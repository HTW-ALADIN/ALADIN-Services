"""Unit tests for graph compilation and conditional routing."""

from core.compiler import CompilerSettings, compile_graph
from core.dsl import GraphDefinition


def _settings(**overrides):
    kwargs = {
        "gateway_base_url": "http://gateway:8002",
        "gateway_api_key": "secret",
        "llm_timeout_seconds": 5.0,
        "llm_retry_once": False,
        "http_timeout_seconds": 5.0,
        "max_tool_response_bytes": 1024,
    }
    kwargs.update(overrides)
    return CompilerSettings(**kwargs)


def _definition(payload):
    return GraphDefinition.model_validate(payload)


async def test_linear_transform_chain_merges_state():
    definition = _definition(
        {
            "name": "chain",
            "nodes": [
                {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]},
                {
                    "id": "b",
                    "type": "transform",
                    "operations": [{"op": "pick", "from_key": "value"}],
                },
            ],
            "edges": [["a", "b"]],
            "entry": "a",
        }
    )
    from core.checkpointer import get_manager

    compiled = compile_graph(definition, _settings(), checkpointer=get_manager().get())
    output = await compiled.ainvoke(
        {"data": {"start": True}}, config={"configurable": {"thread_id": "t1"}}
    )
    assert output["data"]["value"] == 1


async def test_conditional_routing_picks_matching_branch():
    definition = _definition(
        {
            "name": "branch",
            "nodes": [
                {
                    "id": "start",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "go-a"}],
                },
                {
                    "id": "a",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "A"}],
                },
                {
                    "id": "b",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "B"}],
                },
                {
                    "id": "branch",
                    "type": "conditional",
                    "cases": [{"key": "value", "equals": "go-a", "goto": "a"}],
                    "default_goto": "b",
                },
            ],
            "edges": [],
            "conditional_edges": [{"source": "start", "node": "branch"}],
            "entry": "start",
        }
    )
    from core.checkpointer import get_manager

    compiled = compile_graph(definition, _settings(), checkpointer=get_manager().get())
    output = await compiled.ainvoke({"data": {}}, config={"configurable": {"thread_id": "t2"}})
    assert output["data"]["value"] == "A"


async def test_conditional_routing_falls_back_to_default():
    definition = _definition(
        {
            "name": "branch",
            "nodes": [
                {
                    "id": "start",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "other"}],
                },
                {
                    "id": "a",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "A"}],
                },
                {
                    "id": "b",
                    "type": "transform",
                    "operations": [{"op": "const", "value": "B"}],
                },
                {
                    "id": "branch",
                    "type": "conditional",
                    "cases": [{"key": "value", "equals": "go-a", "goto": "a"}],
                    "default_goto": "b",
                },
            ],
            "edges": [],
            "conditional_edges": [{"source": "start", "node": "branch"}],
            "entry": "start",
        }
    )
    from core.checkpointer import get_manager

    compiled = compile_graph(definition, _settings(), checkpointer=get_manager().get())
    output = await compiled.ainvoke({"data": {}}, config={"configurable": {"thread_id": "t3"}})
    assert output["data"]["value"] == "B"
