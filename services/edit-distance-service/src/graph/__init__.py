"""Graph edit distance implementations using NetworkX, GEDLIB (via gedlibpy), and GMatch4py."""

import logging
import time
from typing import Any

import networkx as nx

from ..models import (
    GedPairResult,
    GraphPair,
    GraphRef,
)

logger = logging.getLogger(__name__)

# Exact/anytime/path NetworkX GED is exponential in the worst case. Always
# enforce a bounded timeout so a single request cannot pin a CPU forever;
# clamp caller-supplied values into a sane range.
DEFAULT_GED_TIMEOUT_MS = 5000
MAX_GED_TIMEOUT_MS = 30000


def _resolve_timeout_s(params: dict[str, Any]) -> float:
    """Resolve a clamped, always-positive timeout (in seconds) for GED compute."""
    timeout_ms = params.get("timeout_ms", DEFAULT_GED_TIMEOUT_MS)
    try:
        timeout_ms = float(timeout_ms)
    except (TypeError, ValueError):
        timeout_ms = DEFAULT_GED_TIMEOUT_MS
    if timeout_ms <= 0:
        timeout_ms = DEFAULT_GED_TIMEOUT_MS
    timeout_ms = min(timeout_ms, MAX_GED_TIMEOUT_MS)
    return timeout_ms / 1000


def _error_result(
    pair_id: str,
    exc: Exception,
    elapsed_ms: float,
    *,
    upper_bound: float = float("inf"),
    lower_bound: float = 0.0,
) -> GedPairResult:
    """Build a GedPairResult for a failed computation.

    Logs the full exception server-side, but returns only the exception
    *type* to the API caller (never str(exc)), since backend exception
    messages (especially from C/SWIG-backed gedlibpy) can contain internal
    file paths or object reprs that should not be exposed through the API.
    """
    logger.exception("GED computation failed for pair %s", pair_id)
    return GedPairResult(
        id=pair_id,
        upper_bound=upper_bound,
        lower_bound=lower_bound,
        exact=False,
        runtime_ms=elapsed_ms,
        error=f"computation failed: {type(exc).__name__}",
    )


def _graph_ref_to_nx(graph_ref: GraphRef) -> nx.Graph:
    """Convert a GraphRef to a networkx.Graph.

    Supports three formats: default (nodes+edges), node_link (networkx JSON),
    and adjacency_matrix.
    """
    fmt = graph_ref.format

    # networkx node-link format
    if fmt == "node_link":
        G = nx.Graph() if not graph_ref.directed else nx.DiGraph()
        for node in graph_ref.nodes or []:
            nid = node.get("id", str(node))
            attrs = {k: v for k, v in node.items() if k != "id"}
            G.add_node(nid, **attrs)
        for link in graph_ref.links or []:
            src = link.get("source", link.get("from"))
            dst = link.get("target", link.get("to"))
            attrs = {
                k: v
                for k, v in link.items()
                if k not in ("source", "target", "from", "to")
            }
            G.add_edge(src, dst, **attrs)
        # Also handle the 'edges' field when 'links' is absent (legacy compat)
        for edge in graph_ref.edges or []:
            src = edge.get("source", edge.get("from"))
            dst = edge.get("target", edge.get("to"))
            attrs = {
                k: v
                for k, v in edge.items()
                if k not in ("source", "target", "from", "to")
            }
            G.add_edge(src, dst, **attrs)
        return G

    # adjacency matrix
    if fmt == "adjacency_matrix":
        G = nx.Graph() if not graph_ref.directed else nx.DiGraph()
        mat = graph_ref.matrix or []
        labels = graph_ref.node_labels or [str(i) for i in range(len(mat))]
        for i in range(len(mat)):
            G.add_node(labels[i])
        for i in range(len(mat)):
            for j in range(len(mat[i])):
                # Undirected graphs only need the upper triangle (i <= j);
                # directed graphs must consider every cell, since mat[i][j]
                # and mat[j][i] can represent different edges.
                if mat[i][j] != 0 and (graph_ref.directed or i <= j):
                    G.add_edge(labels[i], labels[j], weight=float(mat[i][j]))
        return G

    # default (nodes+edges)
    G = nx.Graph() if not graph_ref.directed else nx.DiGraph()
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


# ─── NetworkX Backend ─────────────────────────────────────────────────────────


def _networkx_ged_astar(pair: GraphPair, params: dict[str, Any]) -> GedPairResult:
    import networkx as nx

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)
    mode = params.get("mode", "exact")
    timeout_s = _resolve_timeout_s(params)

    node_subst = params.get("node_subst_cost")
    node_del = params.get("node_del_cost")
    node_ins = params.get("node_ins_cost")
    edge_subst = params.get("edge_subst_cost")
    edge_del = params.get("edge_del_cost")
    edge_ins = params.get("edge_ins_cost")

    def _cost(n1_attrs: dict, n2_attrs: dict) -> float:
        return 0.0 if n1_attrs == n2_attrs else 1.0

    # NOTE: NetworkX calls *_subst_cost with two attribute dicts (one per
    # graph) but *_del_cost/*_ins_cost with a single attribute dict (the
    # node/edge being removed or added), so these must not share a signature.
    kwargs = {
        "node_subst_cost": _cost
        if node_subst is None
        else (lambda a, b, _c=node_subst: 0.0 if a == b else _c),
        "node_del_cost": None if node_del is None else (lambda _attrs, _c=node_del: _c),
        "node_ins_cost": None if node_ins is None else (lambda _attrs, _c=node_ins: _c),
        "edge_subst_cost": _cost
        if edge_subst is None
        else (lambda a, b, _c=edge_subst: 0.0 if a == b else _c),
        "edge_del_cost": None if edge_del is None else (lambda _attrs, _c=edge_del: _c),
        "edge_ins_cost": None if edge_ins is None else (lambda _attrs, _c=edge_ins: _c),
        "upper_bound": params.get("upper_bound"),
    }

    t0 = time.perf_counter()
    try:
        if mode == "exact":
            dist = nx.graph_edit_distance(G1, G2, timeout=timeout_s, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            # graph_edit_distance() prunes and returns the best cost found so
            # far when the timeout elapses; it does not return None just
            # because the search was cut short. If we consumed (approximately)
            # the full budget, the result may not be the true optimum, so it
            # must not be reported as exact.
            timed_out = (elapsed / 1000) >= timeout_s
            return GedPairResult(
                id=pair.id,
                upper_bound=dist if dist is not None else float("inf"),
                lower_bound=dist if dist is not None else 0.0,
                exact=dist is not None and not timed_out,
                runtime_ms=elapsed,
            )
        elif mode == "path":
            # optimal_edit_paths() has no timeout and enumerates *all*
            # minimum-cost paths, which can be expensive both in time and
            # memory. Use the bounded, single-best-result generator instead
            # and stop as soon as the clamped timeout elapses.
            gen = nx.optimize_edit_paths(G1, G2, timeout=timeout_s, **kwargs)
            best_node_path, _best_edge_path, cost = None, None, None
            for node_path, edge_path, path_cost in gen:
                best_node_path, _best_edge_path, cost = (
                    node_path,
                    edge_path,
                    path_cost,
                )
                if (time.perf_counter() - t0) >= timeout_s:
                    break
            elapsed = (time.perf_counter() - t0) * 1000
            if best_node_path is not None:
                node_map = [
                    [u, v] for u, v in best_node_path if u is not None or v is not None
                ]
            else:
                node_map = None
            # optimize_edit_paths() is a bounded, anytime search: a result
            # found right as the timeout elapsed is not guaranteed optimal.
            timed_out = (elapsed / 1000) >= timeout_s
            return GedPairResult(
                id=pair.id,
                upper_bound=cost if cost is not None else float("inf"),
                lower_bound=cost if cost is not None else 0.0,
                exact=cost is not None and not timed_out,
                node_map=node_map,
                runtime_ms=elapsed,
            )
        else:  # anytime
            gen = nx.optimize_graph_edit_distance(G1, G2, **kwargs)
            best = float("inf")
            for dist in gen:
                best = dist
                if (time.perf_counter() - t0) >= timeout_s:
                    break
            elapsed = (time.perf_counter() - t0) * 1000
            return GedPairResult(
                id=pair.id,
                upper_bound=best if best != float("inf") else float("inf"),
                lower_bound=0.0,
                exact=False,
                runtime_ms=elapsed,
            )
    except Exception as e:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return _error_result(pair.id, e, elapsed)


# ─── GEDLIB Backend (via gedlibpy) ───────────────────────────────────────────


def _gedlib_apply_edit_costs(env: Any, edit_costs: dict[str, Any]) -> str | None:
    """Best-effort application of user-supplied edit costs to a GEDEnv.

    The exact GEDEnv API for setting per-operation costs is not part of the
    stable, documented gedlibpy surface used elsewhere in this module (only
    add_graph/init/set_method/run_method/get_*_bound/get_node_map are relied
    on). Rather than guess a signature and silently ignore failures, try the
    known candidate methods and report back whether costs were applied so
    callers are never misled into thinking unsupported costs were honored.

    Returns None on success, or a short message describing why costs were
    not applied.
    """
    if not edit_costs:
        return None

    constants = [
        edit_costs.get("node_ins", 1.0),
        edit_costs.get("node_del", 1.0),
        edit_costs.get("node_subst", 1.0),
        edit_costs.get("edge_ins", 1.0),
        edit_costs.get("edge_del", 1.0),
        edit_costs.get("edge_subst", 1.0),
    ]
    for method_name in ("set_edit_costs", "set_edit_cost"):
        method = getattr(env, method_name, None)
        if method is None:
            continue
        try:
            method("CONSTANT", constants)
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("gedlibpy.%s failed: %s", method_name, e)
            return f"edit_costs not applied: {type(e).__name__}"
    return "edit_costs not applied: GEDEnv has no set_edit_cost(s) method"


def _gedlib_compute(
    pair: GraphPair, params: dict[str, Any], *, is_exact: bool = False
) -> GedPairResult:
    """GEDLIB computation shared by ged_astar and ged_heuristic."""
    try:
        import gedlibpy
    except ImportError:
        logger.warning("gedlibpy not installed; returning inf for pair %s", pair.id)
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=0.0,
            error="gedlibpy backend is not installed",
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        env = gedlibpy.GEDEnv()
        _ = env.add_graph(G1)
        _ = env.add_graph(G2)
        cost_error = _gedlib_apply_edit_costs(env, params.get("edit_costs") or {})
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
            error=cost_error,
        )
    except Exception as e:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return _error_result(pair.id, e, elapsed)


def _gmatch4py_resolve_costs(params: dict[str, Any]) -> dict[str, float]:
    """Normalize GMatch4py edit costs to a single shape.

    Accepts either the documented nested ``edit_costs`` mapping or flat
    top-level keys (``node_del``, ``node_ins``, ``edge_del``, ``edge_ins``)
    so all GMatch4py-backed algorithms (GraphEditDistance, HED,
    GreedyEditDistance) honor the same request shape instead of silently
    falling back to defaults depending on which class is used.
    """
    edit_costs = params.get("edit_costs") or {}
    return {
        "node_del": edit_costs.get("node_del", params.get("node_del", 1.0)),
        "node_ins": edit_costs.get("node_ins", params.get("node_ins", 1.0)),
        "edge_del": edit_costs.get("edge_del", params.get("edge_del", 1.0)),
        "edge_ins": edit_costs.get("edge_ins", params.get("edge_ins", 1.0)),
    }


def _gmatch4py_compute(
    pair: GraphPair, params: dict[str, Any], cls_name: str
) -> GedPairResult:
    """GMatch4py computation shared by gmatch4py backends."""
    try:
        import gmatch4py as gm
    except ImportError:
        logger.warning("gmatch4py not installed; returning inf for pair %s", pair.id)
        return GedPairResult(
            id=pair.id,
            upper_bound=float("inf"),
            lower_bound=0.0,
            exact=False,
            runtime_ms=0.0,
            error="gmatch4py backend is not installed",
        )

    G1 = _graph_ref_to_nx(pair.g1)
    G2 = _graph_ref_to_nx(pair.g2)

    t0 = time.perf_counter()
    try:
        cls = getattr(gm, cls_name)
        costs = _gmatch4py_resolve_costs(params)
        inst = cls(
            costs["node_del"],
            costs["node_ins"],
            costs["edge_del"],
            costs["edge_ins"],
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
    except Exception as e:  # noqa: BLE001
        elapsed = (time.perf_counter() - t0) * 1000
        return _error_result(pair.id, e, elapsed)


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
