"""Contract tests for the SageMath Wrapper API.

These tests use FastAPI TestClient and validate the HTTP contract
(endpoints, status codes, response schemas, error handling).
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _mock_sandbox(monkeypatch):
    """Mock run_sandboxed so tests don't need SageMath in the child process."""
    import src.sandbox.executor as exec_mod

    def mock(fn, args, timeout_s=5.0):
        # Route the call to the appropriate inner function based on the args key
        # For SAT
        if "clauses" in args:
            return {"ok": True, "result": {"satisfiable": True, "assignment": {"1": True, "2": True}, "solver": "picosat"}, "error": None}
        # For linalg determinant
        if args.get("matrix") == [[1, 2], [3, 4]]:
            return {"ok": True, "result": {"result": -2, "error": None}, "error": None}
        # For linalg inverse singular
        if args.get("matrix") == [[1, 2], [2, 4]]:
            return {"ok": True, "result": {"result": None, "error": "singular matrix: not invertible"}, "error": None}
        # For optimize
        if "variables" in args:
            return {"ok": True, "result": {"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}, "error": None}
        # For maxima
        if "expression" in args:
            return {"ok": True, "result": {"result": "x^2", "error": None}, "error": None}
        return {"ok": True, "result": None, "error": None}

    monkeypatch.setattr(exec_mod, "run_sandboxed", mock)


# ── SAT ────────────────────────────────────────────────────────────────────

def test_post_sat_solve_returns_200_and_schema(monkeypatch):
    _mock_sandbox(monkeypatch)
    resp = client.post("/v1/sat/solve", json={"clauses": [[1, 2], [-1, 2], [1, -2]]})
    assert resp.status_code == 200
    body = resp.json()
    assert "satisfiable" in body
    assert "assignment" in body
    assert "solver" in body
    assert isinstance(body["satisfiable"], bool)
    assert isinstance(body["assignment"], dict) or body["assignment"] is None
    assert isinstance(body["solver"], str)


def test_post_sat_solve_invalid_payload_returns_422():
    resp = client.post("/v1/sat/solve", json={"clauses": "not-a-list"})
    assert resp.status_code == 422


# ── Linear Algebra ─────────────────────────────────────────────────────────

def test_post_linalg_determinant_returns_200(monkeypatch):
    _mock_sandbox(monkeypatch)
    resp = client.post("/v1/linalg/determinant", json={"matrix": [[1, 2], [3, 4]]})
    assert resp.status_code == 200
    assert resp.json()["result"] == -2


def test_post_linalg_non_square_matrix_returns_400(monkeypatch):
    _mock_sandbox(monkeypatch)
    resp = client.post("/v1/linalg/determinant", json={"matrix": [[1, 2, 3], [4, 5, 6]]})
    assert resp.status_code == 400
    body = resp.json()
    assert "detail" in body
    assert "Traceback" not in body["detail"]  # no stacktrace leak


# ── Optimization ───────────────────────────────────────────────────────────

def test_post_optimize_milp_tutorial_case_returns_200(monkeypatch):
    _mock_sandbox(monkeypatch)
    payload = {
        "variables": ["x", "y"],
        "objective": {"x": 2, "y": 1},
        "maximize": True,
        "constraints": [
            {"coeffs": {"x": 3, "y": 4}, "max": 2.5},
            {"coeffs": {"x": 1.5, "y": 0.5}, "max": 4, "min": 0.5},
        ],
        "var_types": {"x": "real", "y": "real"},
    }
    resp = client.post("/v1/optimize/milp", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["objective_value"] - 1.6666666666666667) < 1e-6


# ── Maxima ─────────────────────────────────────────────────────────────────

def test_post_maxima_eval_rejects_injection_with_400(monkeypatch):
    import src.sandbox.executor as exec_mod
    calls = []
    monkeypatch.setattr(exec_mod, "run_sandboxed", lambda *a, **kw: calls.append(1) or {"ok": True, "result": None, "error": None})

    resp = client.post("/v1/maxima/evaluate", json={
        "expression": "system('rm -rf /')",
        "operation": "simplify",
    })
    assert resp.status_code == 400
    assert "Traceback" not in resp.text
    assert len(calls) == 0, "sandbox was called despite validation failure"


# ── OpenAPI / Health ───────────────────────────────────────────────────────

def test_openapi_json_is_served_and_valid():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "openapi" in body
    paths = body.get("paths", {})
    assert "/v1/sat/solve" in paths
    assert "/v1/linalg/determinant" in paths
    assert "/v1/linalg/inverse" in paths
    assert "/v1/linalg/eigenvalues" in paths
    assert "/v1/linalg/solve" in paths
    assert "/v1/linalg/qr" in paths
    assert "/v1/linalg/lu" in paths
    assert "/v1/linalg/cholesky" in paths
    assert "/v1/linalg/svd" in paths
    assert "/v1/linalg/matrix-exp" in paths
    assert "/v1/linalg/right-kernel" in paths
    assert "/v1/linalg/left-kernel" in paths
    assert "/v1/linalg/charpoly" in paths
    assert "/v1/optimize/milp" in paths
    assert "/v1/optimize/find-root" in paths
    assert "/v1/optimize/minimize" in paths
    assert "/v1/maxima/evaluate" in paths
    assert "/healthz" in paths


def test_health_endpoint():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}