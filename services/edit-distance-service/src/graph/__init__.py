"""Graph edit distance implementations using NetworkX, GEDLIB (via gedlibpy), and GMatch4py."""

import time
from collections.abc import Callable
from typing import Any

import networkx as nx

from ..models import (
    GedPairResult,
    GraphPair,
    GraphRef,
)


def _graph_ref_to_nx(graph_ref: GraphRef) -> nx.Graph:
    """Convert a GraphRef to a networkx.Graph."""
    G = nx.Graph()
    for node in graph_ref.nodes or []:
        nid = node.get("id", str(node))
        attrs = {k: v for k, v in node.items() if k != "id"}
        G.add_node(nid, **attrs)
    for edge in graph_ref.edges or []:
        src = edge.get("source", edge.get("from"))
        dst = edge.get("target", edge.get("to"))
        attrs = {
            k: v for k, v in edge.items() if k not in ("source", "target", "from", "to")
        }
        G.add_edge(src, dst, **attrs)
    return G


def _make_label_aware_cost(
    default_cost: float,
) -> Callable[[dict, dict], float]:
    """Create a cost function that returns 0 for matching labels, else default_cost."""

    def _cost(n1_attrs: dict, n2_attrs: dict) -> float:
        return 0.0 if n1_attrs == n2_attrs else default_cost

    return _cost


# ─── NetworkX Backend ─────────────────────────────────────────────────────────


def _networkx_ged_astar(pair: GraphPair, params: dict[str, Any]) -> GedPairResult:
    import networkx as nx

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)
    mode = params.get("mode", "exact")
    timeout_s = params.get("timeout_ms", 0) / 1000

    # Build label-aware cost functions from explicit costs or defaults
    node_subst = params.get("node_subst_cost")
    node_del = params.get("node_del_cost")
    node_ins = params.get("node_ins_cost")
    edge_subst = params.get("edge_subst_cost")
    edge_del = params.get("edge_del_cost")
    edge_ins = params.get("edge_ins_cost")

    kwargs = {
        "node_subst_cost": _make_label_aware_cost(node_subst)
        if node_subst is not None
        else _make_label_aware_cost(1.0),
        "node_del_cost": _make_label_aware_cost(node_del)
        if node_del is not None
        else None,
        "node_ins_cost": _make_label_aware_cost(node_ins)
        if node_ins is not None
        else None,
        "edge_subst_cost": _make_label_aware_cost(edge_subst)
        if edge_subst is not None
        else _make_label_aware_cost(1.0),
        "edge_del_cost": _make_label_aware_cost(edge_del)
        if edge_del is not None
        else None,
        "edge_ins_cost": _make_label_aware_cost(edge_ins)
        if edge_ins is not None
        else None,
        "upper_bound": params.get("upper_bound"),
    }

    t0 = time.perf_counter()
    try:
        if mode == "exact":
            dist = nx.graph_edit_distance(G1, G2, timeout=timeout_s or None, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=dist if dist is not None else float("inf"),
                lower_bound=dist if dist is not None else 0.0,
                exact=dist is not None,
                runtime_ms=elapsed,
            )
        elif mode == "path":
            paths = list(nx.optimal_edit_paths(G1, G2, **kwargs))
            elapsed = (time.perf_counter() - t0) * 1000
            if paths:
                edit_path, cost = paths[0]
                node_map = [
                    [u, v] for u, v in edit_path if u is not None or v is not None
                ]
            else:
                cost, node_map = None, None
            return GedPairResult(
                id=pair.id,
                upper_bound=cost if cost is not None else float("inf"),
                lower_bound=cost if cost is not None else 0.0,
                exact=cost is not None,
                node_map=node_map,
                runtime_ms=elapsed,
            )
        else:  # anytime
            gen = nx.optimize_graph_edit_distance(G1, G2, **kwargs)
            best = float("inf")
            for dist in gen:
                best = dist
                if (
                    timeout_s
                    and (time.perf_counter() - t0) * 1000 >= params["timeout_ms"]
                ):
                    break
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=best if best != float("inf") else float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )
    except Exception:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


# ─── GEDLIB Backend (via gedlibpy) ───────────────────────────────────────────


def _gedlib_compute(
    pair: GraphPair, params: dict[str, Any], *, is_exact: bool = False
) -> GedPairResult:
    """GEDLIB computation shared by ged_astar and ged_heuristic."""
    try:
        import gedlibpy
    except ImportError:
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        env = gedlibpy.GEDEnv()
        _ = env.add_graph(G1)
        _ = env.add_graph(G2)
        env.init()
        env.set_method(params.get("method", "F2" if is_exact else "BIPARTITE"))
        env.run_method()
        ub = env.get_upper_bound()
        lb = env.get_lower_bound()
        elapsed = (time.perf_counter() - t0) * 1000
        node_map = None
        try:
            node_map = env.get_node_map()
        except Exception:  # noqa: BLE001, S110
            pass
        return GedPairResult(
            id=pair.id,
            upper_bound=ub,
            lower_bound=lb,
            exact=is_exact and ub == lb,
            node_map=node_map,
            runtime_ms=elapsed,
        )
    except Exception:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


def _gmatch4py_compute(
    pair: GraphPair, params: dict[str, Any], cls_name: str
) -> GedPairResult:
    """GMatch4py computation shared by gmatch4py backends."""
    try:
        import gmatch4py as gm
    except ImportError:
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        cls = getattr(gm, cls_name)
        p = params
        if cls_name in ("HED", "GreedyEditDistance"):
            inst = cls(
                p.get("node_del", 1.0),
                p.get("node_ins", 1.0),
                p.get("edge_del", 1.0),
                p.get("edge_ins", 1.0),
            )
        else:
            costs = params.get("edit_costs", {})
            inst = cls(
                costs.get("node_del", 1.0),
                costs.get("node_ins", 1.0),
                costs.get("edge_del", 1.0),
                costs.get("edge_ins", 1.0),
            )
        result_matrix = inst.compare([G1, G2], None)
        distance = result_matrix[0][1]
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=distance,
            lower_bound=distance,
            exact=False,
            runtime_ms=elapsed,
        )
    except Exception:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


# ─── Dispatcher ───────────────────────────────────────────────────────────────

GED_BACKEND_DISPATCH = {
    ("ged_astar", "networkx"): lambda p, params: _networkx_ged_astar(p, params),
    ("ged_astar", "gedlib"): lambda p, params: _gedlib_compute(
        p, params, is_exact=True
    ),
    ("ged_heuristic", "gedlib"): lambda p, params: _gedlib_compute(
        p, params, is_exact=False
    ),
    ("ged_heuristic", "gmatch4py"): lambda p, params: _gmatch4py_compute(
        p, params, "GraphEditDistance"
    ),
    ("ged_hausdorff", "gmatch4py"): lambda p, params: _gmatch4py_compute(
        p, params, "HED"
    ),
    ("ged_greedy", "gmatch4py"): lambda p, params: _gmatch4py_compute(
        p, params, "GreedyEditDistance"
    ),
}


def compute_ged(
    algorithm: str, backend: str, graphs: list[GraphPair], params: dict[str, Any]
) -> list[GedPairResult]:
    """Compute graph edit distance for a batch of graph pairs."""
    key = (algorithm, backend)
    if key not in GED_BACKEND_DISPATCH:
        raise ValueError(
            f"Unsupported algorithm/backend combination: {algorithm}/{backend}"
        )

    func = GED_BACKEND_DISPATCH[key]
    results = []
    for pair in graphs:
        result = func(pair, params)
        results.append(result)

    return results


GED_ALGORITHM_CATALOG = [
    {
        "algorithm": "ged_astar",
        "backend": "networkx",
        "method_options": ["exact", "anytime", "path"],
        "families": [
            "Exact/optimal GED",
            "Anytime approximate GED",
            "Edit-path retrieval",
        ],
        "description": "Exact/A* GED via NetworkX (pure Python, good for small-to-medium graphs)",
    },
    {
        "algorithm": "ged_astar",
        "backend": "gedlib",
        "method_options": ["exact_mip"],
        "families": ["Exact/optimal GED", "Exact via MIP/blackbox"],
        "description": "Exact GED via GEDLIB (F2/BLP methods, C++ core, supports larger graphs)",
    },
    {
        "algorithm": "ged_heuristic",
        "backend": "gedlib",
        "method_options": [
            "BIPARTITE",
            "IPFP",
            "REFINE",
            "ANCHOR_AWARE_GED",
            "BRANCH",
            "NODE",
            "RING",
            "SUBGRAPH",
            "WALKS",
        ],
        "families": [
            "Bipartite (Riesen-Bunke/LSAP) heuristic",
            "IPFP heuristic",
            "Refinement heuristic",
            "Lower-bound heuristic family",
        ],
        "description": "Heuristic GED via GEDLIB (bipartite, IPFP, refine, lower bounds)",
    },
    {
        "algorithm": "ged_heuristic",
        "backend": "gmatch4py",
        "method_options": ["BIPARTITE"],
        "families": ["Bipartite (Riesen-Bunke/LSAP) heuristic"],
        "description": "Bipartite GED via GMatch4py (native networkx.Graph, distance matrix output)",
    },
    {
        "algorithm": "ged_hausdorff",
        "backend": "gmatch4py",
        "method_options": [],
        "families": ["Hausdorff Edit Distance (HED, bounded approximation)"],
        "description": "Hausdorff Edit Distance via GMatch4py (cheap upper-bound pre-filter)",
    },
    {
        "algorithm": "ged_greedy",
        "backend": "gmatch4py",
        "method_options": [],
        "families": ["Greedy edit distance"],
        "description": "Greedy edit distance via GMatch4py (fast assignment-based approximation)",
    },
]
