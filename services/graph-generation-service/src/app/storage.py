from __future__ import annotations

from dataclasses import dataclass

from app.domain import GeneratedGraph
from app.schemas import GraphResource, LabelMode


@dataclass(frozen=True, slots=True)
class StoredGraph:
    resource: GraphResource
    generated: GeneratedGraph
    labels: LabelMode
