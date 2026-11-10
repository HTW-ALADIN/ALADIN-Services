"""Citation Graph Builder — paginated, one BFS level per call.

See core/pagination.py for the HMAC-signed cursor this module produces/consumes,
and unified/repo-integration plan docs for the overall design rationale (no
background job/queue; the entire BFS frontier + visited set travels inside the
cursor so the service itself holds no per-graph state between calls).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from adapters import scimesh_adapter
from config import settings
from core.pagination import GraphCursorState, decode_cursor, encode_cursor
from core.paper import Paper
from core.provider_registry import get_provider_spec

Direction = Literal["citing", "cited_by", "both"]

_SEP = "\x1f"


@dataclass
class Edge:
    from_id: str
    to_id: str
    type: str = "cites"


@dataclass
class GraphPage:
    nodes: list[Paper]
    edges: list[Edge]
    depth_reached: int
    max_depth: int
    done: bool
    cursor: str | None
    truncated: bool
    stats: dict[str, object] = field(default_factory=dict)


def _frontier_key(provider: str, raw_id: str, canonical_id: str) -> str:
    return f"{provider}{_SEP}{raw_id}{_SEP}{canonical_id}"


def _parse_frontier_key(key: str) -> tuple[str, str, str]:
    provider, raw_id, canonical_id = key.split(_SEP)
    return provider, raw_id, canonical_id


async def start(
    seeds: list[tuple[str, str]],
    direction: Direction,
    max_depth: int,
    max_nodes_per_level: int,
    max_total_nodes: int,
    credentials: dict[str, dict[str, str]],
    dedup_enabled: bool = False,
) -> GraphPage:
    """First call: resolve seed papers (depth 0), no cursor yet."""
    nodes: list[Paper] = []
    frontier: list[str] = []
    visited: set[str] = set()
    skipped_no_citation_support: list[str] = []

    for provider, raw_id in seeds:
        spec = get_provider_spec(provider)
        if spec.backend != "scimesh":
            skipped_no_citation_support.append(provider)
            continue
        creds = credentials.get(provider, {})
        paper = await scimesh_adapter.get(provider, creds, raw_id)
        if paper is None:
            continue
        if paper.id in visited:
            continue
        paper = paper.model_copy(update={"depth": 0, "is_seed": True})
        nodes.append(paper)
        visited.add(paper.id)
        if spec.supports_citations:
            frontier.append(_frontier_key(provider, raw_id, paper.id))
        else:
            skipped_no_citation_support.append(provider)

    state = GraphCursorState(
        seeds=tuple(f"{p}{_SEP}{r}" for p, r in seeds),
        direction=direction,
        max_depth=max_depth,
        max_nodes_per_level=max_nodes_per_level,
        max_total_nodes=max_total_nodes,
        frontier=tuple(frontier),
        visited=tuple(visited),
        depth_reached=0,
        total_nodes_emitted=len(nodes),
        dedup_enabled=dedup_enabled,
    )

    done = max_depth <= 0 or not frontier
    cursor = None if done else encode_cursor(settings.graph_cursor_secret, state)

    return GraphPage(
        nodes=nodes,
        edges=[],
        depth_reached=0,
        max_depth=max_depth,
        done=done,
        cursor=cursor,
        truncated=False,
        stats={
            "nodes_by_depth": {"0": len(nodes)},
            "skipped_no_citation_support": sorted(set(skipped_no_citation_support)),
        },
    )


async def advance(cursor: str, credentials: dict[str, dict[str, str]]) -> GraphPage:
    """Subsequent calls: expand one more BFS level from the decoded cursor state."""
    state = decode_cursor(settings.graph_cursor_secret, cursor)

    next_depth = state.depth_reached + 1
    visited = set(state.visited)
    new_nodes: list[Paper] = []
    new_edges: list[Edge] = []
    new_frontier: list[str] = []
    truncated = False
    total_emitted = state.total_nodes_emitted
    level_budget = state.max_nodes_per_level

    directions: list[Direction] = (
        ["citing", "cited_by"] if state.direction == "both" else [state.direction]
    )

    for key in state.frontier:
        provider, raw_id, parent_canonical_id = _parse_frontier_key(key)
        creds = credentials.get(provider, {})

        for sub_direction in directions:
            if len(new_nodes) >= level_budget or total_emitted >= state.max_total_nodes:
                truncated = total_emitted >= state.max_total_nodes
                break

            neighbors = await scimesh_adapter.citations(
                provider,
                creds,
                raw_id,
                sub_direction,
                max_results=level_budget,
            )

            for neighbor in neighbors:
                if sub_direction == "citing":
                    new_edges.append(Edge(from_id=parent_canonical_id, to_id=neighbor.id))
                else:
                    new_edges.append(Edge(from_id=neighbor.id, to_id=parent_canonical_id))

                if neighbor.id in visited:
                    continue
                if len(new_nodes) >= level_budget or total_emitted >= state.max_total_nodes:
                    truncated = total_emitted >= state.max_total_nodes
                    continue

                neighbor = neighbor.model_copy(update={"depth": next_depth, "is_seed": False})
                new_nodes.append(neighbor)
                visited.add(neighbor.id)
                total_emitted += 1

                # Further expansion of this neighbor requires a raw
                # provider-resolvable identifier; a DOI works across all
                # scimesh providers that support citations(), but a neighbor
                # returned without one cannot be expanded in a later level
                # (it still appears as a node -- just as a graph leaf).
                spec = get_provider_spec(provider)
                if spec.supports_citations and neighbor.doi:
                    new_frontier.append(_frontier_key(provider, neighbor.doi, neighbor.id))

    done = (
        next_depth >= state.max_depth or not new_frontier or total_emitted >= state.max_total_nodes
    )

    new_state = GraphCursorState(
        seeds=state.seeds,
        direction=state.direction,
        max_depth=state.max_depth,
        max_nodes_per_level=state.max_nodes_per_level,
        max_total_nodes=state.max_total_nodes,
        frontier=tuple(new_frontier),
        visited=tuple(visited),
        depth_reached=next_depth,
        total_nodes_emitted=total_emitted,
        dedup_enabled=state.dedup_enabled,
    )
    next_cursor = None if done else encode_cursor(settings.graph_cursor_secret, new_state)

    return GraphPage(
        nodes=new_nodes,
        edges=new_edges,
        depth_reached=next_depth,
        max_depth=state.max_depth,
        done=done,
        cursor=next_cursor,
        truncated=truncated,
        stats={"nodes_by_depth": {str(next_depth): len(new_nodes)}},
    )
