"""Compile a validated GraphDefinition into an executable StateGraph.

Engine state is a single `data` dict with a merge reducer, so nodes behave
like pure per-key updates on top of each other. Node functions take and
return *unwrapped* user state (``dict``); the wrapper below translates to and
from the engine's ``{"data": ...}`` channel automatically.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.dsl import ConditionalNode, GraphDefinition
from core.nodes.http_tool import execute_http_node
from core.nodes.llm import execute_llm_node
from core.nodes.transform import execute_transform_node


def _merge_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


class EngineState(TypedDict):
    data: Annotated[dict[str, Any], _merge_data]


class CompilerSettings:
    """Runtime knobs threaded into every compiled node."""

    def __init__(
        self,
        *,
        gateway_base_url: str,
        gateway_api_key: str,
        llm_timeout_seconds: float,
        llm_retry_once: bool,
        http_timeout_seconds: float,
        max_tool_response_bytes: int,
        http_client_factory=None,
        llm_client_factory=None,
    ) -> None:
        self.gateway_base_url = gateway_base_url
        self.gateway_api_key = gateway_api_key
        self.llm_timeout_seconds = llm_timeout_seconds
        self.llm_retry_once = llm_retry_once
        self.http_timeout_seconds = http_timeout_seconds
        self.max_tool_response_bytes = max_tool_response_bytes
        self.http_client_factory = http_client_factory
        self.llm_client_factory = llm_client_factory


def _route_conditional(node: ConditionalNode):
    def _router(state: EngineState) -> str:
        data = state.get("data", {})
        for case in node.cases:
            if data.get(case.key) == case.equals:
                return case.goto
        return node.default_goto

    return _router


def _unwrap(state: EngineState) -> dict[str, Any]:
    return dict(state.get("data", {}))


def _wrap(update: dict[str, Any]) -> dict[str, Any]:
    return {"data": dict(update)}


def compile_graph(
    definition: GraphDefinition, runtime_settings: CompilerSettings, checkpointer=None
):
    """Build and compile a StateGraph. Raises DSLValidationError on bad topology."""
    from core.errors import DSLValidationError

    builder: StateGraph = StateGraph(EngineState)

    for node in definition.nodes:
        if node.type == "llm":
            llm_node = node

            async def _llm(state: EngineState, _node=llm_node):
                client = (
                    runtime_settings.llm_client_factory()
                    if runtime_settings.llm_client_factory
                    else None
                )
                try:
                    return _wrap(
                        await execute_llm_node(
                            _node,
                            _unwrap(state),
                            gateway_base_url=runtime_settings.gateway_base_url,
                            gateway_api_key=runtime_settings.gateway_api_key,
                            timeout_seconds=runtime_settings.llm_timeout_seconds,
                            retry_once=runtime_settings.llm_retry_once,
                            client=client,
                        )
                    )
                finally:
                    if client is not None and hasattr(client, "aclose"):
                        await client.aclose()

            builder.add_node(node.id, _llm)
        elif node.type == "http":
            http_node = node

            async def _http(state: EngineState, _node=http_node):
                client = (
                    runtime_settings.http_client_factory()
                    if runtime_settings.http_client_factory
                    else None
                )
                try:
                    return _wrap(
                        await execute_http_node(
                            _node,
                            _unwrap(state),
                            timeout_seconds=runtime_settings.http_timeout_seconds,
                            max_response_bytes=runtime_settings.max_tool_response_bytes,
                            client=client,
                        )
                    )
                finally:
                    if client is not None and hasattr(client, "aclose"):
                        await client.aclose()

            builder.add_node(node.id, _http)
        elif node.type == "transform":
            transform_node = node

            def _transform(state: EngineState, _node=transform_node):
                return _wrap(execute_transform_node(_node, _unwrap(state)))

            builder.add_node(node.id, _transform)
        elif node.type == "conditional":
            # Conditional nodes never execute: they only route.
            continue
        else:  # pragma: no cover - discriminated union is exhaustive
            raise DSLValidationError(f"unknown node type {node!r}")

    conditional_targets = {edge.node for edge in definition.conditional_edges}
    conditional_sources = {edge.source for edge in definition.conditional_edges}

    builder.add_edge(START, definition.entry)

    for source_id, target_id in definition.edges:
        if source_id in conditional_targets:
            raise DSLValidationError(
                f"conditional node {source_id!r} must be wired via conditional_edges, not edges"
            )
        builder.add_edge(source_id, target_id)

    for edge in definition.conditional_edges:
        target = next(n for n in definition.nodes if n.id == edge.node)
        assert isinstance(target, ConditionalNode)
        mapping = {case.goto: case.goto for case in target.cases}
        mapping[target.default_goto] = target.default_goto
        builder.add_conditional_edges(edge.source, _route_conditional(target), mapping)

    terminal_nodes = {target for _, target in definition.edges} | conditional_sources
    all_sources = {source for source, _ in definition.edges} | conditional_sources
    # Nodes with no outgoing edge terminate the run.
    for node in definition.nodes:
        if node.type == "conditional":
            continue
        if node.id not in all_sources:
            if definition.end is not None and node.id != definition.end:
                continue
            if node.id in terminal_nodes or node.id not in all_sources:
                builder.add_edge(node.id, END)

    return builder.compile(checkpointer=checkpointer)
