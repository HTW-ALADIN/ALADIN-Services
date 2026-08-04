"""Contract tests for the SageMath Wrapper API.

These tests use FastAPI TestClient and validate the HTTP contract
(endpoints, status codes, response schemas, error handling).
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _mock_sandbox(monkeypatch):
    """Mock run_function/run_code in the dispatcher so tests don't need SageMath."""
    from src.registry import dispatcher as disp

    def mock(fn_ref, args, timeout_s=5.0):
        key = fn_ref.split(":", 1)[-1]
        # SAT
        if key == "solve_cnf":
            return {"ok": True, "result": {"satisfiable": True, "assignment": {"1": True, "2": True}, "solver": "picosat"}, "error": None}
        # linalg determinant
        if key == "determinant":
            if args.get("matrix") == [[1, 2, 3], [4, 5, 6]]:
                return {"ok": False, "result": None, "error": "determinant: non-square matrix"}
            return {"ok": True, "result": -2, "error": None}
        # linalg inverse singular
        if key == "inverse":
            if args.get("matrix") == [[1, 2], [2, 4]]:
                return {"ok": False, "result": None, "error": "singular matrix: not invertible"}
            return {"ok": True, "result": None, "error": None}
        # optimize
        if key == "solve_milp":
            return {"ok": True, "result": {"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}, "error": None}
        # maxima
        if key == "evaluate":
            return {"ok": True, "result": "x^2", "error": None}
        return {"ok": True, "result": None, "error": None}

    monkeypatch.setattr(disp, "run_function", mock)


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
    assert resp.json() == -2


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
    from src.registry import dispatcher as disp
    monkeypatch.setattr(disp, "run_function", lambda *a, **kw: {"ok": False, "result": None, "error": "disallowed token 'system' in expression"})

    resp = client.post("/v1/maxima/evaluate", json={
        "expression": "system('rm -rf /')",
        "operation": "simplify",
    })
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


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


# ── Cross-cutting: error handling ─────────────────────────────────────────

def test_404_unknown_path():
    resp = client.get("/v1/nonexistent")
    assert resp.status_code == 404


def test_422_missing_required_field():
    resp = client.post("/v1/linalg/determinant", json={})
    assert resp.status_code == 422


def test_422_invalid_solver(monkeypatch):
    resp = client.post("/v1/sat/solve", json={"clauses": [[1]], "solver": "nope"})
    assert resp.status_code == 422