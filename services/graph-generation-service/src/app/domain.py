from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GeneratedGraph:
    graph: object
    num_nodes: int
    num_edges: int
    directed: bool
