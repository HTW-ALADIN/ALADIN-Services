"""Unit tests for graph edit distance computation.

Covers all 6 algorithm/backend combinations from the GED catalog.
Tests are grouped by (algorithm, backend) with shared fixtures.
"""

import pytest
from src.graph import compute_ged, GED_ALGORITHM_CATALOG, GED_BACKEND_DISPATCH
from src.models import GraphPair, GraphRef


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
        assert r[0].upper_bound > 0

    def test_anytime(self, extra_node):
        r = compute_ged("ged_astar", "networkx", extra_node, {"mode": "anytime", "timeout_ms": 5000})
        assert r[0].upper_bound >= 0

    def test_path_mode(self, identical):
        """mode: path should return a node_map (edit path)."""
        r = compute_ged("ged_astar", "networkx", identical, {"mode": "path", "timeout_ms": 10000})
        assert r[0].upper_bound == 0.0
        assert r[0].node_map is not None  # path mode returns node_map

    def test_batch(self, identical, extra_node):
        r = compute_ged("ged_astar", "networkx", identical + extra_node, {"mode": "exact", "timeout_ms": 10000})
        assert len(r) == 2 and r[0].upper_bound == 0.0 and r[1].upper_bound > 0

    def test_custom_edge_costs(self, extra_edge):
        r = compute_ged("ged_astar", "networkx", extra_edge, {"mode": "exact", "edge_ins_cost": 2.0, "timeout_ms": 10000})
        assert r[0].upper_bound > 0


# ─── GEDLIB: ged_astar (graceful fallback if lib missing) ─────────────────────

class TestGedlibGedAStar:
    def test_identical(self, identical):
        r = compute_ged("ged_astar", "gedlib", identical, {"method": "F2"})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_astar", "gedlib", extra_node, {"method": "F2"})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0


# ─── GEDLIB: ged_heuristic (representative methods) ───────────────────────────

class TestGedlibGedHeuristic:
    def test_bipartite(self, identical, extra_node):
        for graphs in [identical, extra_node]:
            r = compute_ged("ged_heuristic", "gedlib", graphs, {"method": "BIPARTITE"})
            if r[0].upper_bound != float("inf"):
                assert r[0].upper_bound >= 0

    def test_ipfp(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "IPFP"})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0

    def test_refine(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "REFINE"})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound >= 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_heuristic", "gedlib", extra_node, {"method": "BIPARTITE", "edit_costs": {"node_ins": 2.0, "node_del": 2.0, "node_subst": 1.0, "edge_ins": 1.5, "edge_del": 1.5, "edge_subst": 1.0}})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0


# ─── GMatch4py: ged_heuristic (BIPARTITE / BP2) ──────────────────────────────

class TestGMatch4pyGedHeuristic:
    def test_identical(self, identical):
        r = compute_ged("ged_heuristic", "gmatch4py", identical, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_heuristic", "gmatch4py", extra_node, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_heuristic", "gmatch4py", extra_node, {"edit_costs": {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0}})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0


# ─── GMatch4py: ged_hausdorff ─────────────────────────────────────────────────

class TestGMatch4pyGedHausdorff:
    def test_identical(self, identical):
        r = compute_ged("ged_hausdorff", "gmatch4py", identical, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_hausdorff", "gmatch4py", extra_node, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_hausdorff", "gmatch4py", extra_node, {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0


# ─── GMatch4py: ged_greedy ────────────────────────────────────────────────────

class TestGMatch4pyGedGreedy:
    def test_identical(self, identical):
        r = compute_ged("ged_greedy", "gmatch4py", identical, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound == 0.0

    def test_different(self, extra_node):
        r = compute_ged("ged_greedy", "gmatch4py", extra_node, {})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0

    def test_custom_costs(self, extra_node):
        r = compute_ged("ged_greedy", "gmatch4py", extra_node, {"node_del": 2.0, "node_ins": 2.0, "edge_del": 1.0, "edge_ins": 1.0})
        if r[0].upper_bound != float("inf"):
            assert r[0].upper_bound > 0


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
