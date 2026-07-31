"""Comprehensive end-to-end test scenarios for the SageMath Wrapper.

Diese Tests bilden reale mathematische Workflows ab und prüfen die
gesamte Kette: HTTP → FastAPI → dynamische Routen → Dispatcher → Sandbox.
Die SageMath-Aufrufe werden gemockt, damit die Tests ohne echte SageMath-
Installation laufen. Die mathematischen Ergebnisse sind aber so gewählt,
dass sie den echten SageMath-Resultaten entsprechen.

Jedes Szenario testet mehrere zusammenhängende Operationen.
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


# ==============================================================================
# Sandbox-Mock — dispatches anhand fn.__name__
# ==============================================================================


def _mock_run_sandboxed(fn, args, timeout_s=5.0):
    name = fn.__name__ if hasattr(fn, "__name__") else "?"
    if name == "_solve_cnf_inner":      return _mock_sat(args)
    if name == "_det_inner":            return _mock_linalg_result(args["matrix"], "det")
    if name == "_inv_inner":            return _mock_linalg_result(args["matrix"], "inv")
    if name == "_eig_inner":            return _mock_linalg_result(args["matrix"], "eig")
    if name == "_solve_inner":          return _mock_solve(args["a"], args["b"])
    if name == "_qr_inner":             return _mock_linalg_result(args["matrix"], "qr")
    if name == "_lu_inner":             return _mock_linalg_result(args["matrix"], "lu")
    if name == "_cholesky_inner":       return _mock_linalg_result(args["matrix"], "chol")
    if name == "_svd_inner":            return _mock_linalg_result(args["matrix"], "svd")
    if name == "_exp_inner":            return _mock_linalg_result(args["matrix"], "exp")
    if name == "_rk_inner":             return _mock_linalg_result(args["matrix"], "rk")
    if name == "_lk_inner":             return _mock_linalg_result(args["matrix"], "lk")
    if name == "_charpoly_inner":       return _mock_linalg_result(args["matrix"], "cp")
    if name == "_milp_inner":           return _mock_milp(args)
    if name == "_find_root_inner":      return _mock_find_root(args)
    if name == "_minimize_inner":       return _mock_minimize(args)
    if name == "_evaluate_inner":       return _mock_maxima(args)
    return {"ok": True, "result": None, "error": None}


def _mock_sat(args):
    clauses = args["clauses"]
    solver = args.get("solver", "picosat")
    data = {
        ((1,),): {"satisfiable": True, "assignment": {"1": True}, "solver": solver},
        ((1,), (-1,)): {"satisfiable": False, "assignment": None, "solver": solver},
        ((1, 2), (-1, 2), (1, -2)): {"satisfiable": True, "assignment": {"1": True, "2": True}, "solver": solver},
        ((1, 2), (-1, 2), (1, -2), (-1, -2)): {"satisfiable": False, "assignment": None, "solver": solver},
        ((1, -2, 3), (-1, 2, 3), (1, 2, -3)): {"satisfiable": True, "assignment": {"1": True, "2": True, "3": True}, "solver": solver},
        ((),): {"satisfiable": False, "assignment": None, "solver": solver},
    }
    key = tuple(tuple(c) for c in clauses)
    result = data.get(key, {"satisfiable": True, "assignment": {"1": True, "2": False}, "solver": solver})
    return {"ok": True, "result": result, "error": None}


_LINALG = {
    ("det", ((1, 2), (3, 4))): (-2.0, None),
    ("det", ((1, 2), (2, 4))): (0.0, None),
    ("inv", ((1, 2), (3, 4))): ([[-2.0, 1.0], [1.5, -0.5]], None),
    ("inv", ((1, 2), (2, 4))): (None, "singular matrix: not invertible"),
    ("eig", ((1, 2), (3, 4))): ([-0.372, 5.372], None),
    ("cp", ((1, 2), (3, 4))): ("x^2 - 5*x - 2", None),
    ("qr", ((1, 2), (3, 4))): ({"Q": [[-0.316, -0.949], [-0.949, 0.316]], "R": [[-3.162, -4.427], [0.0, -0.632]]}, None),
    ("lu", ((4, 3), (6, 3))): ({"P": [[0.0, 1.0], [1.0, 0.0]], "L": [[1.0, 0.0], [0.667, 1.0]], "U": [[6.0, 3.0], [0.0, 1.0]]}, None),
    ("chol", ((4, 2), (2, 3))): ([[2.0, 0.0], [1.0, 1.414]], None),
    ("svd", ((1, 2), (3, 4))): ({"U": [[-0.405, -0.915], [-0.915, 0.405]], "Sigma": [5.465, 0.366], "V": [[-0.576, 0.817], [-0.817, -0.576]]}, None),
    ("exp", ((1, 0), (0, 1))): ([[2.718, 0.0], [0.0, 2.718]], None),
    ("rk", ((1, 2), (2, 4))): ([[-2.0, 1.0]], None),
    ("lk", ((1, 2), (2, 4))): ([[1.0, -0.5]], None),
}


def _mock_linalg_result(matrix, op):
    key = (op, tuple(tuple(r) for r in matrix))
    entry = _LINALG.get(key)
    if entry:
        val, err = entry
        return {"ok": True, "result": {"result": val, "error": err}, "error": None}
    return {"ok": True, "result": {"result": None, "error": "no result"}, "error": None}


def _mock_solve(a, b):
    key = (tuple(tuple(r) for r in a), tuple(b))
    if key == (((3, 2), (1, 2)), (1, 1)):
        return {"ok": True, "result": {"result": [0.0, 0.5], "error": None}, "error": None}
    return {"ok": True, "result": {"result": [], "error": None}, "error": None}


def _mock_milp(args):
    v, obj, maxi, cons = args["variables"], args["objective"], args["maximize"], args["constraints"]
    vt = args.get("var_types", {})

    if v == ["x", "y"] and obj == {"x": 2, "y": 1} and maxi and len(cons) >= 1 and cons[0] == {"coeffs": {"x": 3, "y": 4}, "max": 2.5}:
        return {"ok": True, "result": {"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}, "error": None}
    if v == ["x"] and obj == {"x": 1} and maxi and cons == [{"coeffs": {"x": 2}, "max": 3}] and vt.get("x") == "integer":
        return {"ok": True, "result": {"status": "optimal", "objective_value": 1.0, "values": {"x": 1}}, "error": None}
    if v == ["x"] and len(cons) == 2 and cons[0].get("max") == 1 and cons[1].get("min") == 5:
        return {"ok": True, "result": {"status": "infeasible", "objective_value": None, "values": None}, "error": None}
    if v == ["x"] and obj == {"x": 1} and maxi and cons == []:
        return {"ok": True, "result": {"status": "unbounded", "objective_value": None, "values": None}, "error": None}
    return {"ok": True, "result": {"status": "error", "objective_value": None, "values": None}, "error": None}


def _mock_find_root(args):
    expr = args["expression"]
    val = {"x - 2": 2.0, "x^2 - 4": 2.0}.get(expr)
    if val is not None:
        return {"ok": True, "result": {"result": val, "error": None}, "error": None}
    return {"ok": True, "result": {"result": None, "error": "no root found"}, "error": None}


def _mock_minimize(args):
    if args["expression"] == "x^2 + y^2" and tuple(args["x0"]) == (1.0, 1.0):
        return {"ok": True, "result": {"result": [0.0, 0.0], "error": None}, "error": None}
    return {"ok": True, "result": {"result": None, "error": "minimization failed"}, "error": None}


def _mock_maxima(args):
    op, expr, bounds = args["operation"], args["expression"], args.get("bounds")
    if op == "simplify":
        return {"ok": True, "result": {"result": "0", "error": None}, "error": None}
    if op == "differentiate":
        return {"ok": True, "result": {"result": "3*x^2*sin(x) + x^3*cos(x)", "error": None}, "error": None}
    if op == "integrate":
        if bounds is not None:
            if expr == "x" and bounds == [0, 2]:
                return {"ok": True, "result": {"result": 2.0, "error": None}, "error": None}
            return {"ok": True, "result": {"result": 0.333, "error": None}, "error": None}
        return {"ok": True, "result": {"result": "x^2", "simplify": "x^2", "error": None}, "error": None}
    if op == "solve":
        return {"ok": True, "result": {"result": ["x == 2", "x == -2"], "error": None}, "error": None}
    if op == "limit":
        return {"ok": True, "result": {"result": "1", "error": None}, "error": None}
    if op == "series":
        return {"ok": True, "result": {"result": "x - 1/6*x^3 + 1/120*x^5 + O(x^6)", "error": None}, "error": None}
    if op == "laplace":
        return {"ok": True, "result": {"result": "2/s^3", "error": None}, "error": None}
    return {"ok": True, "result": {"result": None, "error": f"unknown op '{op}'"}, "error": None}


# ==============================================================================
# Fixture
# ==============================================================================

@pytest.fixture
def mock_sandbox(monkeypatch):
    import src.sandbox.executor as exec_mod
    monkeypatch.setattr(exec_mod, "run_sandboxed", _mock_run_sandboxed)


# ==============================================================================
# SZENARIO 1: Linear-Algebra-Workflow
# ==============================================================================

class TestLinalgWorkflow:
    """Kompletter Linear-Algebra-Workflow: [[1,2],[3,4]] analysieren.

    HTTP-Response-Format: {"result": <wert>, "error": None}
    """

    M = [[1, 2], [3, 4]]

    def test_determinant(self, mock_sandbox):
        r = client.post("/v1/linalg/determinant", json={"matrix": self.M})
        assert r.status_code == 200
        assert r.json()["result"] == -2.0

    def test_inverse_roundtrip(self, mock_sandbox):
        r = client.post("/v1/linalg/inverse", json={"matrix": self.M})
        assert r.status_code == 200
        inv = r.json()["result"]
        assert abs(inv[0][0] - (-2.0)) < 1e-9
        assert abs(inv[1][1] - (-0.5)) < 1e-9
        n = len(self.M)
        prod = [[sum(self.M[i][k] * inv[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
        for i in range(n):
            for j in range(n):
                assert abs(prod[i][j] - (1.0 if i == j else 0.0)) < 1e-9

    def test_eigenvalues(self, mock_sandbox):
        r = client.post("/v1/linalg/eigenvalues", json={"matrix": self.M})
        assert r.status_code == 200
        assert len(r.json()["result"]) == 2

    def test_charpoly(self, mock_sandbox):
        r = client.post("/v1/linalg/charpoly", json={"matrix": self.M})
        assert r.status_code == 200
        cp = r.json()["result"]
        assert "x^2" in cp and "5" in cp and "2" in cp

    def test_singular_matrix(self, mock_sandbox):
        s = [[1, 2], [2, 4]]
        r = client.post("/v1/linalg/determinant", json={"matrix": s})
        assert r.status_code == 200 and r.json()["result"] == 0.0
        r = client.post("/v1/linalg/inverse", json={"matrix": s})
        assert r.json()["result"] is None and "singular" in r.json()["error"].lower()

    def test_linear_system(self, mock_sandbox):
        r = client.post("/v1/linalg/solve", json={"a": [[3, 2], [1, 2]], "b": [1, 1]})
        assert r.status_code == 200
        sol = r.json()["result"]
        assert abs(sol[0]) < 1e-9 and abs(sol[1] - 0.5) < 1e-9


# ==============================================================================
# SZENARIO 2: SAT-Workflow
# ==============================================================================

class TestSatWorkflow:
    def test_satisfiable(self, mock_sandbox):
        r = client.post("/v1/sat/solve", json={
            "clauses": [[1, -2, 3], [-1, 2, 3], [1, 2, -3]], "solver": "picosat"})
        assert r.status_code == 200 and r.json()["satisfiable"] is True

    def test_unsatisfiable(self, mock_sandbox):
        r = client.post("/v1/sat/solve", json={"clauses": [[1], [-1]]})
        assert r.status_code == 200 and r.json()["satisfiable"] is False

    def test_solver_selection(self, mock_sandbox):
        for s in ["picosat", "cryptominisat", "glucose"]:
            r = client.post("/v1/sat/solve", json={
                "clauses": [[1, 2], [-1, 2], [1, -2]], "solver": s})
            assert r.status_code == 200 and r.json()["solver"] == s

    def test_default_solver(self, mock_sandbox):
        r = client.post("/v1/sat/solve", json={"clauses": [[1]]})
        assert r.status_code == 200 and r.json()["solver"] == "picosat"


# ==============================================================================
# SZENARIO 3: Optimierungs-Workflow
# ==============================================================================

class TestOptimizationWorkflow:
    """max 2x + y, 3x + 4y ≤ 2.5, x,y ≥ 0 → x=0.833, y=0, obj=1.667."""

    def test_milp_optimal(self, mock_sandbox):
        r = client.post("/v1/optimize/milp", json={
            "variables": ["x", "y"], "objective": {"x": 2, "y": 1},
            "maximize": True, "constraints": [{"coeffs": {"x": 3, "y": 4}, "max": 2.5}],
            "var_types": {"x": "real", "y": "real"}})
        assert r.status_code == 200
        b = r.json()
        assert b["status"] == "optimal"
        assert abs(b["objective_value"] - 1.6666666666666667) < 1e-9
        assert abs(b["values"]["x"] - 0.8333333333333334) < 1e-9

    def test_milp_constraints(self, mock_sandbox):
        r = client.post("/v1/optimize/milp", json={
            "variables": ["x", "y"], "objective": {"x": 2, "y": 1},
            "maximize": True, "constraints": [{"coeffs": {"x": 3, "y": 4}, "max": 2.5}],
            "var_types": {"x": "real", "y": "real"}})
        assert r.status_code == 200
        x, y = r.json()["values"]["x"], r.json()["values"]["y"]
        assert 3*x + 4*y <= 2.5 + 1e-9 and x >= 0 and y >= 0

    def test_milp_integer(self, mock_sandbox):
        r = client.post("/v1/optimize/milp", json={
            "variables": ["x"], "objective": {"x": 1}, "maximize": True,
            "constraints": [{"coeffs": {"x": 2}, "max": 3}], "var_types": {"x": "integer"}})
        assert r.status_code == 200 and r.json()["values"]["x"] == 1

    def test_milp_infeasible(self, mock_sandbox):
        r = client.post("/v1/optimize/milp", json={
            "variables": ["x"], "objective": {"x": 1}, "maximize": True,
            "constraints": [{"coeffs": {"x": 1}, "max": 1}, {"coeffs": {"x": 1}, "min": 5}],
            "var_types": {"x": "real"}})
        assert r.status_code == 200 and r.json()["status"] == "infeasible"

    def test_milp_unbounded(self, mock_sandbox):
        r = client.post("/v1/optimize/milp", json={
            "variables": ["x"], "objective": {"x": 1}, "maximize": True,
            "constraints": [], "var_types": {"x": "real"}})
        assert r.status_code == 200 and r.json()["status"] == "unbounded"

    def test_find_root(self, mock_sandbox):
        r = client.post("/v1/optimize/find-root", json={
            "expression": "x - 2", "variable": "x", "a": 0, "b": 5})
        assert r.status_code == 200
        assert r.json()["result"] == 2.0

    def test_minimize(self, mock_sandbox):
        r = client.post("/v1/optimize/minimize", json={
            "expression": "x^2 + y^2", "variables": ["x", "y"], "x0": [1.0, 1.0]})
        assert r.status_code == 200
        assert r.json()["result"] == [0.0, 0.0]


# ==============================================================================
# SZENARIO 4: Maxima-Workflow
# ==============================================================================

class TestMaximaWorkflow:
    def test_simplify(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "(x + 1)^2 - (x^2 + 2*x + 1)",
            "operation": "simplify", "variable": "x"})
        assert r.status_code == 200 and r.json()["result"] == "0"

    def test_differentiate(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "x^3 * sin(x)", "operation": "differentiate", "variable": "x"})
        assert r.status_code == 200
        s = r.json()["result"]
        assert "x^2" in s and "sin" in s and "cos" in s

    def test_integral_definite(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "x", "operation": "integrate", "variable": "x", "bounds": [0, 2]})
        assert r.status_code == 200 and abs(r.json()["result"] - 2.0) < 1e-9

    def test_solve_equation(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "x^2 - 4", "operation": "solve", "variable": "x"})
        assert r.status_code == 200
        sols = r.json()["result"]
        assert any("2" in s for s in sols) and any("-2" in s for s in sols)

    def test_limit(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "sin(x)/x", "operation": "limit", "variable": "x"})
        assert r.status_code == 200 and "1" in str(r.json()["result"])

    def test_series(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "sin(x)", "operation": "series", "variable": "x"})
        assert r.status_code == 200
        s = r.json()["result"]
        assert "x" in s and "O(x" in s

    def test_laplace(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "t^2", "operation": "laplace", "variable": "t"})
        assert r.status_code == 200
        s = r.json()["result"]
        assert "2" in s and "s" in s

    def test_injection_blocked(self, monkeypatch):
        import src.sandbox.executor as exec_mod
        calls = []
        monkeypatch.setattr(exec_mod, "run_sandboxed", lambda *a, **kw: calls.append(1) or {"ok": True, "result": None, "error": None})
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "system('rm -rf /')", "operation": "simplify", "variable": "x"})
        assert r.status_code == 400
        assert len(calls) == 0
        assert "Traceback" not in r.text

    def test_unknown_operation(self, mock_sandbox):
        r = client.post("/v1/maxima/evaluate", json={
            "expression": "x^2", "operation": "do_harm", "variable": "x"})
        assert r.status_code == 422


# ==============================================================================
# SZENARIO 5: Cross-Cutting Integration
# ==============================================================================

class TestCrossCutting:
    def test_health(self, mock_sandbox):
        assert client.get("/healthz").json() == {"status": "ok"}

    def test_openapi_paths(self, mock_sandbox):
        paths = client.get("/openapi.json").json()["paths"]
        for p in ["/v1/sat/solve", "/v1/linalg/determinant", "/v1/linalg/inverse",
                  "/v1/linalg/eigenvalues", "/v1/linalg/solve", "/v1/linalg/qr",
                  "/v1/linalg/lu", "/v1/linalg/cholesky", "/v1/linalg/svd",
                  "/v1/linalg/matrix-exp", "/v1/linalg/right-kernel",
                  "/v1/linalg/left-kernel", "/v1/linalg/charpoly",
                  "/v1/linalg/kernel", "/v1/linalg/echelon_form", "/v1/linalg/rank",
                  "/v1/linalg/matrix_vector_product", "/v1/linalg/vector_matrix_product",
                  "/v1/optimize/milp", "/v1/optimize/find-root", "/v1/optimize/minimize",
                  "/v1/maxima/evaluate", "/healthz"]:
            assert p in paths, f"Fehlt: {p}"

    def test_422_invalid_type(self, mock_sandbox):
        assert client.post("/v1/linalg/determinant", json={"matrix": "nope"}).status_code == 422

    def test_422_missing_field(self, mock_sandbox):
        assert client.post("/v1/linalg/determinant", json={}).status_code == 422

    def test_404_unknown(self, mock_sandbox):
        assert client.get("/v1/nonexistent").status_code == 404

    def test_400_non_square(self, mock_sandbox):
        r = client.post("/v1/linalg/determinant", json={"matrix": [[1, 2, 3], [4, 5, 6]]})
        assert r.status_code == 400 and "square" in r.json()["detail"].lower()

    def test_no_stacktrace_leak(self, mock_sandbox):
        r = client.post("/v1/linalg/determinant", json={"matrix": [[1, 2, 3], [4, 5, 6]]})
        assert "Traceback" not in r.text

    def test_422_invalid_solver(self, mock_sandbox):
        r = client.post("/v1/sat/solve", json={"clauses": [[1]], "solver": "nope"})
        assert r.status_code == 422


# ==============================================================================
# SZENARIO 6: Template-basierte Endpunkte
# ==============================================================================

class TestTemplateEndpoints:
    """Template-Endpunkte: run_sandboxed_code muss in dispatcher gepatcht werden."""

    def test_rank(self, monkeypatch):
        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_sandboxed_code",
                            lambda c, timeout_s=5.0: {"ok": True, "result": 2, "error": None})
        assert client.post("/v1/linalg/rank", json={"matrix": [[1, 2], [3, 4]]}).json() == 2

    def test_kernel_nullspace(self, monkeypatch):
        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_sandboxed_code",
                            lambda c, timeout_s=5.0: {"ok": True, "result": [[-2.0, 1.0]], "error": None})
        v = client.post("/v1/linalg/kernel", json={"matrix": [[1, 2], [2, 4]]}).json()[0]
        assert abs(1*v[0] + 2*v[1]) < 1e-9 and abs(2*v[0] + 4*v[1]) < 1e-9

    def test_matrix_vector_product(self, monkeypatch):
        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_sandboxed_code",
                            lambda c, timeout_s=5.0: {"ok": True, "result": [3.0, 7.0], "error": None})
        r = client.post("/v1/linalg/matrix_vector_product", json={
            "matrix": [[1, 2], [3, 4]], "vector": [1, 1]})
        assert r.json() == [3.0, 7.0]


# ==============================================================================
# SZENARIO 7: CLI-Contract
# ==============================================================================

class TestCliContract:
    """CLI und API liefern identische Ergebnisse (gleicher Dispatcher)."""

    def test_determinant_matches_api(self, monkeypatch):
        from typer.testing import CliRunner
        from src.cli.main import app as cli_app
        import src.sandbox.executor as exec_mod
        monkeypatch.setattr(exec_mod, "run_sandboxed", _mock_run_sandboxed)

        cli = CliRunner().invoke(cli_app, ["linalg", "determinant", "--matrix", "[[1,2],[3,4]]"])
        assert cli.exit_code == 0
        api = client.post("/v1/linalg/determinant", json={"matrix": [[1, 2], [3, 4]]})
        assert json.loads(cli.stdout) == api.json()

    def test_sat_matches_api(self, monkeypatch):
        from typer.testing import CliRunner
        from src.cli.main import app as cli_app
        import src.sandbox.executor as exec_mod
        monkeypatch.setattr(exec_mod, "run_sandboxed", _mock_run_sandboxed)

        cli = CliRunner().invoke(cli_app, ["sat", "solve", "--clauses", "[[1,2],[-1,2],[1,-2]]"])
        assert cli.exit_code == 0
        api = client.post("/v1/sat/solve", json={"clauses": [[1, 2], [-1, 2], [1, -2]]})
        assert json.loads(cli.stdout) == api.json()

    def test_cli_invalid_json(self, monkeypatch):
        from typer.testing import CliRunner
        from src.cli.main import app as cli_app
        import src.sandbox.executor as exec_mod
        monkeypatch.setattr(exec_mod, "run_sandboxed", _mock_run_sandboxed)
        r = CliRunner().invoke(cli_app, ["sat", "solve", "--clauses", "not json"])
        assert r.exit_code != 0
        assert "Traceback" not in (r.stdout + r.stderr)

    def test_cli_optimize_spec_file(self, monkeypatch, tmp_path):
        from typer.testing import CliRunner
        from src.cli.main import app as cli_app
        import src.sandbox.executor as exec_mod
        monkeypatch.setattr(exec_mod, "run_sandboxed", _mock_run_sandboxed)

        spec = {"variables": ["x", "y"], "objective": {"x": 2, "y": 1},
                "maximize": True, "constraints": [{"coeffs": {"x": 3, "y": 4}, "max": 2.5}],
                "var_types": {"x": "real", "y": "real"}}
        sf = tmp_path / "p.json"
        sf.write_text(json.dumps(spec))
        r = CliRunner().invoke(cli_app, ["optimize", "milp", "--spec-file", str(sf)])
        assert r.exit_code == 0
        b = json.loads(r.stdout)
        assert b["status"] == "optimal"
        assert abs(b["objective_value"] - 1.6666666666666667) < 1e-9