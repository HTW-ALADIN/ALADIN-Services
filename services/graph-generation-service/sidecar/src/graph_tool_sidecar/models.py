from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class SidecarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal[
        "configuration_model",
        "stochastic_block_model",
        "knn_graph",
        "triangulation",
        "price_network",
    ]
    params: dict[str, Any]
    directed: bool = False


class SidecarGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[int]
    edges: list[tuple[int, int]]
    directed: bool
