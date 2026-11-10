from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import settings
from core.paper import Paper


class GraphSeed(BaseModel):
    provider: str
    paper_id: str


class GraphRequest(BaseModel):
    seeds: list[GraphSeed] = Field(default_factory=list)
    direction: Literal["citing", "cited_by", "both"] = "both"
    max_depth: int = Field(default=settings.graph_max_depth_default, ge=0, le=5)
    max_nodes_per_level: int = Field(
        default=settings.graph_max_nodes_per_level_default, ge=1, le=1000
    )
    max_total_nodes: int = Field(default=settings.graph_max_total_nodes_default, ge=1, le=20000)
    credentials: dict[str, dict[str, str]] = Field(default_factory=dict)
    dedup_enabled: bool = False
    cursor: str | None = None
    """Opaque token from a previous /v1/graph response. When present, `seeds`
    and the other expansion parameters are ignored -- they are already
    encoded in the cursor."""


class GraphEdgeSchema(BaseModel):
    from_id: str = Field(serialization_alias="from")
    to_id: str = Field(serialization_alias="to")
    type: str = "cites"

    model_config = {"populate_by_name": True}


class GraphResponse(BaseModel):
    nodes: list[Paper]
    edges: list[GraphEdgeSchema]
    depth_reached: int
    max_depth: int
    done: bool
    cursor: str | None
    truncated: bool
    stats: dict[str, object] = Field(default_factory=dict)
