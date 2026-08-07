"""Unit tests for graph edit distance computation.

Covers all 6 algorithm/backend combinations from the GED catalog.
Tests are grouped by (algorithm, backend) with shared fixtures.
"""

import importlib.util

import networkx as nx
import pytest
from src.graph import (
    GED_ALGORITHM_CATALOG,
    GED_BACKEND_DISPATCH,
    _graph_ref_to_nx,
    compute_ged,
)
from src.models import GraphPair, GraphRef

requires_gedlibpy = pytest.mark.skipif(
    importlib.util.find_spec("gedlibpy") is None,
    reason="gedlibpy is not installed (optional [graph] extra)",
)
requires_gmatch4py = pytest.mark.skipif(
    importlib.util.find_spec("gmatch4py") is None,
    reason="gmatch4py is not installed (optional [graph] extra)",
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _pair(pair_id, g1_nodes, g1_edges, g2_nodes, g2_edges):
    return GraphPair(id=pair_id, g1=GraphRef(nodes=g1_nodes, edges=g1_edges), g2=GraphRef(nodes=g2_nodes, edges=g2_edges))

@pytest.fixture
def identical():
    return [_pair("identical", [{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}], [{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}])]

@pytest.fixture
def extra_node():
    return [_pair("extra_node", [{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}], [{"id": "A"}, {"id": "B"}, {"id": "C"}], [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}])]

@pytest.fixture
def extra_edge():
    return [_pair("extra_edge", [{"id": "A"}, {"id": "B"}, {"id": "C"}], [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}], [{"id": "A"}, {"id": "B"}, {"id": "C"}], [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}, {"source": "A", "target": "C"}])]

@pytest.fixture
def different():
    return [_pair("different", [{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}], [{"id": "X"}, {"id": "Y"}], [])]

@pytest.fixture
def single_node():
    return [_pair("single", [{"id": "A"}], [], [{"id": "B"}], [])]


# ─── Catalog tests ────────────────────────────────────────────────────────────

class TestCatalog:
    def test_has_entries(self):
        assert len(GED_ALGORITHM_CATALOG) > 0

    def test_catalog_matches_dispatch(self):
        cat = {(e["algorithm"], e["backend"]) for e in GED_ALGORITHM_CATALOG}
        assert cat == set(GED_BACKEND_DISPATCH.keys())


# ─── NetworkX: ged_astar (exact + anytime) ────────────────────────────────────

class TestNetworkXGedAStar:
    def test_identical(self, identical):
        r = compute_ged("ged_astar", "networkx", identical, {"mode": "exact", "timeout_ms": 10000})
        assert r[0].upper_bound == 0.0 and r[0].lower_bound == 0.0 and r[0].exact

    def test_extra_node(self, extra_node):
        r = compute_ged("ged_astar", "networkx", extra_node, {"mode": "exact", "timeout_ms": 10000})
        assert r[0].upper_bound > 0

    def test_extra_edge(self, extra_edge):
        r = compute_ged("ged_astar", "networkx", extra_edge, {"mode": "exact", "timeout_ms": 10000})
        assert r[0].upper_bound > 0

    def test_different(self, different):
        r = compute_ged("ged_astar", "networkx", different, {"mode": "exact", "timeout_ms": 10000})
        assert r[0].upper_bound > 0

    def test_single_node(self, single_node):
        r = compute_ged("ged_astar", "networkx", single_node, {"mode": "exact", "timeout_ms": 10000})
        # Unlabeled single-node graphs: same structure (no edges, no labels) -> GED=0
        # Different node IDs don't matter without labels
        assert r[0].upper_bound == 0.0

    def test_anytime(self, extra_node):
        r = compute_ged("ged_astar", "networkx", extra_node, {"mode": "anytime", "timeout_ms": 5000})
        assert r[0].upper_bound >= 0

    def test_path_mode(self, identical):
        """mode: path should attempt edit path retrieval."""
        r = compute_ged("ged_astar", "networkx", identical, {"mode": "path", "timeout_ms": 10000})
        # optimal_edit_paths for identical graphs may timeout; verify it ran
        assert r[0].runtime_ms >= 0

    def test_exact_mode_completes_within_budget_reports_exact_true(self, identical):
        """When the search finishes well inside the timeout, the result is
        genuinely optimal and must be reported as exact."""
        r = compute_ged("ged_astar", "networkx", identical, {"mode": "exact", "timeout_ms": 10000})
        assert r[0].exact is True

    def test_exact_mode_timeout_reports_exact_false(self, identical, monkeypatch):
        """graph_edit_distance() prunes and returns the best-so-far cost when
        the timeout elapses; it does NOT return None just because the search
        was cut short. A timed-out result must never be reported as exact
        (regression test for the exact:true mislabeling bug)."""
        import src.graph as graph_module

        # First perf_counter() call is t0; every call after simulates a
        # clock far past the (default 5s) timeout, regardless of how fast
        # the real computation actually was.
        state = {"n": 0}

        def fake_perf_counter():
            state["n"] += 1
            return 0.0 if state["n"] == 1 else 999.0

        monkeypatch.setattr(graph_module.time, "perf_counter", fake_perf_counter)

        r = compute_ged("ged_astar", "networkx", identical, {"mode": "exact"})
        assert r[0].upper_bound == 0.0  # a result was still found...
        assert r[0].exact is False  # ...but must not be labeled exact

    def test_path_mode_timeout_reports_exact_false(self, identical, monkeypatch):
        import src.graph as graph_module

        state = {"n": 0}

        def fake_perf_counter():
            state["n"] += 1
            return 0.0 if state["n"] == 1 else 999.0

        monkeypatch.setattr(graph_module.time, "perf_counter", fake_perf_counter)

        r = compute_ged("ged_astar", "networkx", identical, {"mode": "path"})
        assert r[0].exact is False

    def test_batch(self, identical, extra_node):
        r = compute_ged("ged_astar", "networkx", identical + extra_node, {"mode": "exact", "timeout_ms": 10000})
        assert len(r) == 2 and r[0].upper_bound == 0.0 and r[1].upper_bound > 0

    def test_custom_edge_costs(self, extra_edge):
        """extra_edge differs by exactly one inserted edge; a custom
        edge_ins_cost must be reflected exactly in the resulting distance
        (regression test for the node/edge cost callable arity bug)."""
        r = compute_ged("ged_astar", "networkx", extra_edge, {"mode": "exact", "edge_ins_cost": 2.0, "timeout_ms": 10000})
        assert r[0].error is None
        assert r[0].upper_bound == 2.0

    def test_custom_node_costs(self, extra_node):
        """extra_node differs by exactly one inserted node (and its edge);
        a custom node_ins_cost must be added on top of the default edge
        insertion cost of 1.0."""
        r = compute_ged("ged_astar", "networkx", extra_node, {"mode": "exact", "node_ins_cost": 3.0, "timeout_ms": 10000})
        assert r[0].error is None
        assert r[0].upper_bound == 4.0


# ─── GEDLIB: ged_astar (skipped if gedlibpy is not installed) ─────────────────

@requires_gedlibpy
class TestGedlibGedAStar:
    def test_identical(self, identical):
        r = compute_ged("ged_astar", "gedlib", identical, {"method": "F2"})
        assert r[0].error is None
        assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_astar", "gedlib", extra_node, {"method": "F2"})
        assert r[0].error is None
        assert r[0].upper_bound > 0


# ─── GEDLIB: ged_heuristic (representative methods) ───────────────────────────

@requires_gedlibpy
class TestGedlibGedHeuristic:
    def test_bipartite(self, identical, extra_node):
        for graphs in [identical, extra_node]:
            r = compute_ged("ged_heuristic", "gedlib", graphs, {"method": "BIPARTITE"})
            assert r[0].error is None
            assert r[0].upper_bound >= 0

    def test_ipfp(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "IPFP"})
        assert r[0].error is None
        assert r[0].upper_bound > 0

    def test_refine(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "REFINE"})
        assert r[0].error is None
        assert r[0].upper_bound >= 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "BIPARTITE", "edit_costs": {"node_ins": 2.0, "node_del": 2.0, "node_subst": 1.0, "edge_ins": 1.5, "edge_del": 1.5, "edge_subst": 1.0}})
        assert r[0].error is None
        assert r[0].upper_bound > 0


# ─── GMatch4py: ged_heuristic (BIPARTITE / BP2) ──────────────────────────────

@requires_gmatch4py
class TestGMatch4pyGedHeuristic:
    def test_identical(self, identical):
        r = compute_ged("ged_heuristic", "gmatch4py", identical, {})
        assert r[0].error is None
        assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_heuristic", "gmatch4py", extra_node, {})
        assert r[0].error is None
        assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_heuristic", "gmatch4py", extra_node, {"edit_costs": {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0}})
        assert r[0].error is None
        assert r[0].upper_bound > 0


# ─── GMatch4py: ged_hausdorff ─────────────────────────────────────────────────

@requires_gmatch4py
class TestGMatch4pyGedHausdorff:
    def test_identical(self, identical):
        r = compute_ged("ged_hausdorff", "gmatch4py", identical, {})
        assert r[0].error is None
        assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_hausdorff", "gmatch4py", extra_node, {})
        assert r[0].error is None
        assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_hausdorff", "gmatch4py", extra_node, {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0})
        assert r[0].error is None
        assert r[0].upper_bound > 0


# ─── GMatch4py: ged_greedy ────────────────────────────────────────────────────

@requires_gmatch4py
class TestGMatch4pyGedGreedy:
    def test_identical(self, identical):
        r = compute_ged("ged_greedy", "gmatch4py", identical, {})
        assert r[0].error is None
        assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_greedy", "gmatch4py", extra_node, {})
        assert r[0].error is None
        assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_greedy", "gmatch4py", extra_node, {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0})
        assert r[0].error is None
        assert r[0].upper_bound > 0


# ─── Directed graph handling ──────────────────────────────────────────────────


class TestDirectedGraphs:
    """Regression tests: `directed` must be honored for every input format,
    not just node_link."""

    def test_default_format_directed_produces_digraph(self):
        ref = GraphRef(
            nodes=[{"id": "A"}, {"id": "B"}],
            edges=[{"source": "A", "target": "B"}],
            directed=True,
        )
        G = _graph_ref_to_nx(ref)
        assert isinstance(G, nx.DiGraph)
        assert G.has_edge("A", "B")
        assert not G.has_edge("B", "A")

    def test_default_format_undirected_is_symmetric(self):
        ref = GraphRef(
            nodes=[{"id": "A"}, {"id": "B"}],
            edges=[{"source": "A", "target": "B"}],
        )
        G = _graph_ref_to_nx(ref)
        assert not isinstance(G, nx.DiGraph)
        assert G.has_edge("A", "B") and G.has_edge("B", "A")

    def test_adjacency_matrix_directed_produces_digraph(self):
        ref = GraphRef(
            format="adjacency_matrix",
            matrix=[[0, 1], [0, 0]],
            node_labels=["A", "B"],
            directed=True,
        )
        G = _graph_ref_to_nx(ref)
        assert isinstance(G, nx.DiGraph)
        assert G.has_edge("A", "B")
        assert not G.has_edge("B", "A")

    def test_adjacency_matrix_directed_uses_full_matrix(self):
        # Asymmetric matrix: mat[1][0] (B->A) is set but mat[0][1] (A->B) is
        # not. An undirected/upper-triangle-only reading would miss this
        # lower-triangle edge entirely.
        ref = GraphRef(
            format="adjacency_matrix",
            matrix=[[0, 0], [1, 0]],
            node_labels=["A", "B"],
            directed=True,
        )
        G = _graph_ref_to_nx(ref)
        assert G.has_edge("B", "A")
        assert not G.has_edge("A", "B")


# ─── Error cases ──────────────────────────────────────────────────────────────

class TestErrors:
    def test_unknown_algorithm(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_ged("nonexistent", "networkx", [], {})

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_ged("ged_astar", "nonexistent", [], {})

    def test_valid_algorithm_wrong_backend(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_ged("ged_hausdorff", "networkx", [], {})

    def test_empty_graphs(self):
        r = compute_ged("ged_astar", "networkx", [], {"mode": "exact"})
        assert r == []

    def test_empty_graph(self):
        g = _pair("empty", [], [], [], [])
        r = compute_ged("ged_astar", "networkx", [g], {"mode": "exact", "timeout_ms": 10000})
        assert r[0].upper_bound == 0.0
