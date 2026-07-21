"""Graph edit distance implementations using NetworkX, GEDLIB (via gedlibpy), and GMatch4py."""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..models import (
    GedPairResult,
    GraphPair,
    GraphRef,
)


def _graph_ref_to_nx(graph_ref: GraphRef) -> Any:
    """Convert a GraphRef (inline or by reference) to a networkx.Graph."""
    import networkx as nx

    if graph_ref.nodes is not None:
        G = nx.Graph()
        for node in graph_ref.nodes:
            nid = node.get("id", str(node))
            attrs = {k: v for k, v in node.items() if k != "id"}
            G.add_node(nid, **attrs)
        if graph_ref.edges:
            for edge in graph_ref.edges:
                src = edge.get("source", edge.get("from"))
                dst = edge.get("target", edge.get("to"))
                attrs = {k: v for k, v in edge.items() if k not in ("source", "target", "from", "to")}
                G.add_edge(src, dst, **attrs)
        return G
    elif graph_ref.graph_ref:
        # Could resolve from companion graph-generation service
        # For now, raise not implemented
        raise NotImplementedError("Graph reference resolution not yet implemented")
    else:
        raise ValueError("GraphRef must have either 'nodes' or 'graph_ref'")


# ─── NetworkX Backend ─────────────────────────────────────────────────────────

def _networkx_ged_astar(pair: GraphPair, params: dict) -> GedPairResult:
    import networkx as nx

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)
    mode = params.get("mode", "exact")
    timeout_ms = params.get("timeout_ms")

    t0 = time.perf_counter()

    node_subst = params.get("node_subst_cost")
    node_del = params.get("node_del_cost")
    node_ins = params.get("node_ins_cost")
    edge_subst = params.get("edge_subst_cost")
    edge_del = params.get("edge_del_cost")
    edge_ins = params.get("edge_ins_cost")

    def _make_cost_dict(base_cost, default_name):
        """Helper to create cost callable from optional float."""
        if base_cost is not None:
            return lambda n1, n2: base_cost
        return None

    # Handle cost functions
    node_subst_fn = _make_cost_dict(node_subst, "node_subst")
    node_del_fn = _make_cost_dict(node_del, "node_del")
    node_ins_fn = _make_cost_dict(node_ins, "node_ins")
    edge_subst_fn = _make_cost_dict(edge_subst, "edge_subst")
    edge_del_fn = _make_cost_dict(edge_del, "edge_del")
    edge_ins_fn = _make_cost_dict(edge_ins, "edge_ins")

    if mode == "exact":
        try:
            dist = nx.graph_edit_distance(
                G1, G2,
                node_subst_cost=node_subst_fn,
                node_del_cost=node_del_fn,
                node_ins_cost=node_ins_fn,
                edge_subst_cost=edge_subst_fn,
                edge_del_cost=edge_del_fn,
                edge_ins_cost=edge_ins_fn,
                upper_bound=params.get("upper_bound"),
                timeout=timeout_ms / 1000 if timeout_ms else None,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=dist if dist is not None else float("inf"),
                lower_bound=dist if dist is not None else 0.0,
                exact=dist is not None,
                runtime_ms=elapsed,
            )
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )

    elif mode == "path":
        try:
            paths = list(nx.optimal_edit_paths(
                G1, G2,
                node_subst_cost=node_subst_fn,
                node_del_cost=node_del_fn,
                node_ins_cost=node_ins_fn,
                edge_subst_cost=edge_subst_fn,
                edge_del_cost=edge_del_fn,
                edge_ins_cost=edge_ins_fn,
                upper_bound=params.get("upper_bound"),
            ))
            elapsed = (time.perf_counter() - t0) * 1000
            if paths:
                # paths[0] = (edit_path, cost) where edit_path = list of (u, v) pairs
                edit_path, cost = paths[0]
                node_map = [[u, v] for u, v in edit_path if u is not None or v is not None]
            else:
                cost = None
                node_map = None
            return GedPairResult(
                id=pair.id,
                upper_bound=cost if cost is not None else float("inf"),
                lower_bound=cost if cost is not None else 0.0,
                exact=cost is not None,
                node_map=node_map,
                runtime_ms=elapsed,
            )
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )

    elif mode == "anytime":
        try:
            gen = nx.optimize_graph_edit_distance(
                G1, G2,
                node_subst_cost=node_subst_fn,
                node_del_cost=node_del_fn,
                node_ins_cost=node_ins_fn,
                edge_subst_cost=edge_subst_fn,
                edge_del_cost=edge_del_fn,
                edge_ins_cost=edge_ins_fn,
                upper_bound=params.get("upper_bound"),
            )
            best = float("inf")
            for dist in gen:
                best = dist
                elapsed = (time.perf_counter() - t0) * 1000
                if timeout_ms and elapsed >= timeout_ms:
                    break
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=best if best != float("inf") else float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )

    elapsed = (time.perf_counter() - t0) * 1000
    return GedPairResult(
        id=pair.id,
        upper_bound=float("inf"),
        lower_bound=0.0,
        exact=False,
        runtime_ms=elapsed,
    )


# ─── GEDLIB Backend (via gedlibpy) ───────────────────────────────────────────

def _gedlib_ged_astar(pair: GraphPair, params: dict) -> GedPairResult:
    """GEDLIB exact/A* via MIP or F2 method."""
    try:
        import gedlibpy
    except ImportError:
        return GedPairResult(
            id=pair.id, upper_bound=float("inf"), lower_bound=0.0,
            exact=False, runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        env = gedlibpy.GEDEnv()
        id1 = env.add_graph(G1)
        id2 = env.add_graph(G2)
        env.init()

        method = params.get("method", "F2")
        env.set_method(method)
        env.run_method()

        ub = env.get_upper_bound()
        lb = env.get_lower_bound()
        elapsed = (time.perf_counter() - t0) * 1000

        node_map = None
        try:
            node_map = env.get_node_map()
        except Exception:
            pass

        return GedPairResult(
            id=pair.id,
            upper_bound=ub,
            lower_bound=lb,
            exact=ub == lb,
            node_map=node_map,
            runtime_ms=elapsed,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


def _gedlib_ged_heuristic(pair: GraphPair, params: dict) -> GedPairResult:
    """GEDLIB heuristic methods (BIPARTITE, IPFP, REFINE, etc.)."""
    try:
        import gedlibpy
    except ImportError:
        return GedPairResult(
            id=pair.id, upper_bound=float("inf"), lower_bound=0.0,
            exact=False, runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        env = gedlibpy.GEDEnv()
        id1 = env.add_graph(G1)
        id2 = env.add_graph(G2)
        env.init()

        method = params.get("method", "BIPARTITE")
        env.set_method(method)
        env.run_method()

        ub = env.get_upper_bound()
        lb = env.get_lower_bound()
        elapsed = (time.perf_counter() - t0) * 1000

        node_map = None
        try:
            node_map = env.get_node_map()
        except Exception:
            pass

        return GedPairResult(
            id=pair.id,
            upper_bound=ub,
            lower_bound=lb,
            exact=False,
            node_map=node_map,
            runtime_ms=elapsed,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


# ─── GMatch4py Backend ───────────────────────────────────────────────────────

def _gmatch4py_ged_heuristic(pair: GraphPair, params: dict) -> GedPairResult:
    """GMatch4py BIPARTITE (BP2) heuristic."""
    try:
        import gmatch4py as gm
    except ImportError:
        return GedPairResult(
            id=pair.id, upper_bound=float("inf"), lower_bound=0.0,
            exact=False, runtime_ms=0.0,
        )

    import networkx as nx

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        costs = params.get("edit_costs", {})
        ged = gm.GraphEditDistance(
            costs.get("node_del", 1.0),
            costs.get("node_ins", 1.0),
            costs.get("edge_del", 1.0),
            costs.get("edge_ins", 1.0),
        )
        # GMatch4py operates on lists of graphs
        result_matrix = ged.compare([G1, G2], None)
        distance = result_matrix[0][1]  # upper triangular
        elapsed = (time.perf_counter() - t0) * 1000

        return GedPairResult(
            id=pair.id,
            upper_bound=distance,
            lower_bound=distance,
            exact=False,
            runtime_ms=elapsed,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


def _gmatch4py_ged_hausdorff(pair: GraphPair, params: dict) -> GedPairResult:
    """GMatch4py Hausdorff Edit Distance (HED)."""
    try:
        import gmatch4py as gm
    except ImportError:
        return GedPairResult(
            id=pair.id, upper_bound=float("inf"), lower_bound=0.0,
            exact=False, runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        p = params
        hed = gm.HED(
            p.get("node_del", 1.0),
            p.get("node_ins", 1.0),
            p.get("edge_del", 1.0),
            p.get("edge_ins", 1.0),
        )
        result_matrix = hed.compare([G1, G2], None)
        distance = result_matrix[0][1]
        elapsed = (time.perf_counter() - t0) * 1000

        return GedPairResult(
            id=pair.id,
            upper_bound=distance,
            lower_bound=distance,
            exact=False,
            runtime_ms=elapsed,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=elapsed,
        )


def _gmatch4py_ged_greedy(pair: GraphPair, params: dict) -> GedPairResult:
    """GMatch4py Greedy Edit Distance."""
    try:
        import gmatch4py as gm
    except ImportError:
        return GedPairResult(
            id=pair.id, upper_bound=float("inf"), lower_bound=0.0,
            exact=False, runtime_ms=0.0,
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        p = params
        greedy = gm.GreedyEditDistance(
            p.get("node_del", 1.0),
            p.get("node_ins", 1.0),
            p.get("edge_del", 1.0),
            p.get("edge_ins", 1.0),
        )
        result_matrix = greedy.compare([G1, G2], None)
        distance = result_matrix[0][1]
        elapsed = (time.perf_counter() - t0) * 1000

        return GedPairResult(
            id=pair.id,
            upper_bound=distance,
            lower_bound=distance,
            exact=False,
            runtime_ms=elapsed,
        )
    except Exception as e:
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
    ("ged_astar", "networkx"): _networkx_ged_astar,
    ("ged_astar", "gedlib"): _gedlib_ged_astar,
    ("ged_heuristic", "gedlib"): _gedlib_ged_heuristic,
    ("ged_heuristic", "gmatch4py"): _gmatch4py_ged_heuristic,
    ("ged_hausdorff", "gmatch4py"): _gmatch4py_ged_hausdorff,
    ("ged_greedy", "gmatch4py"): _gmatch4py_ged_greedy,
}


def compute_ged(algorithm: str, backend: str, graphs: list[GraphPair], params: dict) -> list[GedPairResult]:
    """Compute graph edit distance for a batch of graph pairs."""
    key = (algorithm, backend)
    if key not in GED_BACKEND_DISPATCH:
        raise ValueError(f"Unsupported algorithm/backend combination: {algorithm}/{backend}")

    func = GED_BACKEND_DISPATCH[key]
    results = []
    for pair in graphs:
        result = func(pair, params)
        results.append(result)

    return results


GED_ALGORITHM_CATALOG = [
    {"algorithm": "ged_astar", "backend": "networkx", "method_options": ["exact", "anytime", "path"],
     "families": ["Exact/optimal GED", "Anytime approximate GED", "Edit-path retrieval"],
     "description": "Exact/A* GED via NetworkX (pure Python, good for small-to-medium graphs)"},
    {"algorithm": "ged_astar", "backend": "gedlib", "method_options": ["exact_mip"],
     "families": ["Exact/optimal GED", "Exact via MIP/blackbox"],
     "description": "Exact GED via GEDLIB (F2/BLP methods, C++ core, supports larger graphs)"},
    {"algorithm": "ged_heuristic", "backend": "gedlib",
     "method_options": ["BIPARTITE", "IPFP", "REFINE", "ANCHOR_AWARE_GED", "BRANCH", "NODE", "RING", "SUBGRAPH", "WALKS"],
     "families": ["Bipartite (Riesen-Bunke/LSAP) heuristic", "IPFP heuristic", "Refinement heuristic", "Lower-bound heuristic family"],
     "description": "Heuristic GED via GEDLIB (bipartite, IPFP, refine, lower bounds)"},
    {"algorithm": "ged_heuristic", "backend": "gmatch4py", "method_options": ["BIPARTITE"],
     "families": ["Bipartite (Riesen-Bunke/LSAP) heuristic"],
     "description": "Bipartite GED via GMatch4py (native networkx.Graph, distance matrix output)"},
    {"algorithm": "ged_hausdorff", "backend": "gmatch4py", "method_options": [],
     "families": ["Hausdorff Edit Distance (HED, bounded approximation)"],
     "description": "Hausdorff Edit Distance via GMatch4py (cheap upper-bound pre-filter)"},
    {"algorithm": "ged_greedy", "backend": "gmatch4py", "method_options": [],
     "families": ["Greedy edit distance"],
     "description": "Greedy edit distance via GMatch4py (fast assignment-based approximation)"},
]