from __future__ import annotations

from math import isfinite
from typing import Any

from graph_safety.limits import LIMITS, ResourceLimitError


def validate_budget(
    algorithm: str, params: dict[str, Any], nodes: int, directed: bool, *, expected_edges: float = 0
) -> None:
    """Conservative admission estimates, backed by hard worker and result limits."""

    def inspect(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for name, item in value.items():
                inspect(item, name)
        elif isinstance(value, list):
            for item in value:
                inspect(item, key)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not isfinite(value):
                raise ResourceLimitError("numeric parameters must be finite", 400)
            if key not in {"seed", "low", "high", "points"} and abs(value) > LIMITS.work:
                raise ResourceLimitError("numeric parameter exceeds the work budget")

    inspect(params)
    dimension = params.get("dim", 1)
    if dimension > 64:
        raise ResourceLimitError("point and lattice dimensions must not exceed 64")
    if params.get("points") and len(params["points"][0]) > 64:
        raise ResourceLimitError("point dimensions must not exceed 64")
    n = nodes
    dense = n * n if directed else n * (n + 1) // 2
    edges: float = dense
    work: float = n * n
    variant = params.get("variant")
    if algorithm in {"forest_fire", "kleinberg_small_world"}:
        # Use sparse estimates with dedicated Kleinberg size/dimension guards;
        # hard worker limits bound execution for both models.
        edges = expected_edges
        work = max(n, edges)
    elif algorithm == "classic_deterministic":
        shape = params["shape"]
        edges = dense if shape == "complete" else n * (params.get("n", 1) or 1) if shape == "hypercube" else 4 * n
        work = edges
    elif algorithm in {"barabasi_albert", "price_network", "powerlaw_cluster"}:
        edges = n * (params.get("m") or params.get("k") or 1)
        work = edges
    elif algorithm == "erdos_renyi_gnm":
        edges = params["m"]
        work = edges
    elif algorithm == "kronecker_rmat":
        edges = n * params["edgeFactor"]
        work = edges
    elif algorithm in {"configuration_model", "chung_lu"}:
        sequence = params.get("sequence") or params.get("out") or params.get("degreeSequence") or []
        edges = sum(sequence) / (1 if directed else 2)
        work = max(n * n, 2 * edges * params.get("numSwitchesPerEdge", 1))
    elif algorithm == "random_regular":
        edges = n * (params.get("d") or params.get("k") or 1)
        work = max(edges, n * n)
    elif algorithm == "random_tree":
        edges = n
        work = n * params.get("tries", 1)
    elif algorithm == "knn_graph":
        edges = n * params["k"]
        dimensions = len(params["points"][0]) if params.get("points") else params["pointGenerator"]["dimensions"]
        work = n * n * dimensions * max(1, params.get("maxIter", 0))
    elif algorithm == "triangulation":
        dimensions = len(params["points"][0]) if params.get("points") else params["pointGenerator"]["dimensions"]
        edges = 3 * n if dimensions == 2 else dense
    elif algorithm == "static_fitness":
        edges = params["m"]
        work = max(n * n, edges)
    elif algorithm == "watts_strogatz":
        neighbors = params.get("k") or 2 * (params.get("nNeighbors") or params.get("nei") or 1)
        edges = n * neighbors * dimension
        work = edges * (params.get("tries") or 100 if variant == "connected" else 1)
    elif algorithm == "growing_attachment" and (params.get("m") or params.get("k")):
        edges = n * (params.get("m") or params["k"])
        work = max(n * n, edges)
    elif algorithm == "random_bipartite":
        edges = params["m"] if params.get("m") is not None else params["n1"] * params["n2"] * (2 if directed else 1)
    elif algorithm == "stochastic_block_model" and "matrix" in params:
        edges = max(dense, sum(sum(row) for row in params["matrix"]))
        work = max(work, edges, sum(params.get("outDegrees") or []), sum(params.get("inDegrees") or []))
    work = max(work, n * dimension)
    if edges > LIMITS.edges:
        raise ResourceLimitError("graph exceeds the estimated edge budget")
    if work > LIMITS.work:
        raise ResourceLimitError("graph exceeds the estimated work budget")
