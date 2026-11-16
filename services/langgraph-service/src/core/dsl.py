"""Graph definition DSL: validated, data-only description of a StateGraph.

Never `eval`/`exec` caller input: nodes are a closed set of primitive types
(`llm`, `http`, `transform`, `conditional`) with `$.path` lookups only.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, allow_inf_nan=False)


MAX_NODES = 32
MAX_EDGES = 64

_NODE_IDS_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class LLMNode(StrictBaseModel):
    id: str = Field(pattern=_NODE_IDS_PATTERN)
    type: Literal["llm"]
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    system: str | None = Field(default=None, max_length=8000)
    input_key: str | None = Field(default=None, max_length=128)
    prompt_template: str | None = Field(default=None, max_length=8000)
    output_key: str = Field(min_length=1, max_length=128)
    max_output_tokens: int | None = Field(default=None, ge=1, le=128000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def _validate_prompt_source(self) -> LLMNode:
        if self.input_key is None and self.prompt_template is None:
            raise ValueError("one of input_key or prompt_template is required")
        return self


class HTTPNode(StrictBaseModel):
    id: str = Field(pattern=_NODE_IDS_PATTERN)
    type: Literal["http"]
    url: str = Field(min_length=1, max_length=2048)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] | None = None
    query_params: dict[str, str] | None = None
    output_key: str = Field(min_length=1, max_length=128)
    timeout_ms: int | None = Field(default=None, ge=100, le=600000)

    @model_validator(mode="after")
    def _validate_headers(self) -> HTTPNode:
        forbidden = {"authorization", "cookie", "proxy-authorization"}
        for name in self.headers:
            lowered = name.lower()
            if lowered in forbidden:
                raise ValueError(f"header {name!r} is not allowed on http nodes")
            if lowered != "content-type":
                raise ValueError(f"only Content-Type headers are allowed, got {name!r}")
            value = self.headers[name]
            if "application/json" not in value.lower():
                raise ValueError("Content-Type must be application/json")
        if len(self.headers) > 4:
            raise ValueError("at most 4 headers are allowed")
        return self


class TransformPick(StrictBaseModel):
    op: Literal["pick"]
    from_key: str = Field(min_length=1, max_length=128)
    path: str | None = Field(default=None, max_length=512)


class TransformConst(StrictBaseModel):
    op: Literal["const"]
    value: Any


class TransformMerge(StrictBaseModel):
    op: Literal["merge"]
    keys: list[str] = Field(min_length=1, max_length=32)


TransformOperation = Annotated[
    TransformPick | TransformConst | TransformMerge, Field(discriminator="op")
]


class TransformNode(StrictBaseModel):
    id: str = Field(pattern=_NODE_IDS_PATTERN)
    type: Literal["transform"]
    operations: list[TransformOperation] = Field(min_length=1, max_length=32)
    output_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConditionalCase(StrictBaseModel):
    key: str = Field(min_length=1, max_length=128)
    equals: Any
    goto: str = Field(min_length=1, max_length=64)


class ConditionalNode(StrictBaseModel):
    id: str = Field(pattern=_NODE_IDS_PATTERN)
    type: Literal["conditional"]
    cases: list[ConditionalCase] = Field(min_length=1, max_length=16)
    default_goto: str = Field(min_length=1, max_length=64)


GraphNode = Annotated[
    LLMNode | HTTPNode | TransformNode | ConditionalNode, Field(discriminator="type")
]


class ConditionalEdge(StrictBaseModel):
    source: str = Field(min_length=1, max_length=64)
    node: str = Field(min_length=1, max_length=64)


class GraphDefinition(StrictBaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    state_schema: dict[str, Any] | None = None
    nodes: list[GraphNode] = Field(min_length=1, max_length=MAX_NODES)
    edges: list[list[str]] = Field(default_factory=list, max_length=MAX_EDGES)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list, max_length=16)
    entry: str = Field(min_length=1, max_length=64)
    end: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def _validate_topology(self) -> GraphDefinition:
        from core.errors import DSLValidationError

        node_ids = [node.id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise DSLValidationError("node ids must be unique")
        node_set = set(node_ids)

        if self.entry not in node_set:
            raise DSLValidationError(f"entry {self.entry!r} is not a defined node")
        entry_node = next(n for n in self.nodes if n.id == self.entry)
        if entry_node.type == "conditional":
            raise DSLValidationError("entry must not be a conditional node")

        if self.end is not None and self.end not in node_set:
            raise DSLValidationError(f"end {self.end!r} is not a defined node")

        for edge in self.edges:
            if len(edge) != 2:
                raise DSLValidationError("edges must be [from, to] pairs")
            for endpoint in edge:
                if endpoint not in node_set:
                    raise DSLValidationError(f"edge endpoint {endpoint!r} is not a defined node")
            for endpoint in edge:
                endpoint_node = next(n for n in self.nodes if n.id == endpoint)
                if endpoint_node.type == "conditional":
                    raise DSLValidationError(
                        f"conditional node {endpoint!r} must be wired via conditional_edges, "
                        "not edges"
                    )

        for cond_edge in self.conditional_edges:
            if cond_edge.source not in node_set:
                raise DSLValidationError(
                    f"conditional edge source {cond_edge.source!r} is not a defined node"
                )
            if cond_edge.node not in node_set:
                raise DSLValidationError(
                    f"conditional edge node {cond_edge.node!r} is not a defined node"
                )
            target = next(n for n in self.nodes if n.id == cond_edge.node)
            if target.type != "conditional":
                raise DSLValidationError(
                    f"conditional edge target {cond_edge.node!r} must be a conditional node"
                )

        for node in self.nodes:
            if node.type == "conditional":
                destinations = [case.goto for case in node.cases] + [node.default_goto]
                for destination in destinations:
                    if destination not in node_set:
                        raise DSLValidationError(
                            f"conditional node {node.id!r} routes to unknown node {destination!r}"
                        )
                    dest_node = next(n for n in self.nodes if n.id == destination)
                    if dest_node.type == "conditional":
                        raise DSLValidationError(
                            f"conditional node {node.id!r} must not route to conditional node "
                            f"{destination!r}"
                        )
        return self


def lookup_path(state: dict[str, Any], path: str) -> Any:
    """Resolve a `$.a.b.0.c` lookup against a flat/nested JSON state.

    Only dotted key navigation and non-negative integer list indexes are
    supported; anything else raises ValueError. Never evaluates expressions.
    """
    from core.errors import DSLValidationError

    if not path.startswith("$."):
        raise DSLValidationError(f"path must start with '$.'; got {path!r}")
    current: Any = state
    for segment in path[2:].split("."):
        if segment == "":
            raise DSLValidationError(f"invalid empty path segment in {path!r}")
        if isinstance(current, list):
            if not segment.isdigit():
                raise DSLValidationError(f"cannot index list with {segment!r} in {path!r}")
            index = int(segment)
            if index >= len(current):
                raise DSLValidationError(f"index {index} out of range in {path!r}")
            current = current[index]
        elif isinstance(current, dict):
            if segment not in current:
                raise DSLValidationError(f"key {segment!r} not present for path {path!r}")
            current = current[segment]
        else:
            raise DSLValidationError(f"cannot traverse into scalar for path {path!r}")
    return current
