"""Contract tests for the CLI interface.

Uses Typer's CliRunner and compares CLI output with API responses where applicable.
"""

import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.api.main import app as api_app
from src.cli.main import app as cli_app

runner = CliRunner()
api_client = TestClient(api_app)


def _mock_sandbox(monkeypatch):
    """Mock run_function in the dispatcher so tests don't need SageMath."""
    from src.registry import dispatcher as disp

    def mock_function(fn_ref, args, timeout_s=5.0):
        key = fn_ref.split(":", 1)[-1]
        if key == "solve_cnf":
            return {"ok": True, "result": {"satisfiable": True, "assignment": {"1": True, "2": True}, "solver": "picosat"}, "error": None}
        if key == "determinant":
            return {"ok": True, "result": -2, "error": None}
        if key == "solve_milp":
            return {"ok": True, "result": {"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}, "error": None}
        if key == "evaluate":
            return {"ok": True, "result": "x^2", "error": None}
        return {"ok": True, "result": None, "error": None}

    monkeypatch.setattr(disp, "run_function", mock_function)


def test_cli_sat_solve_matches_core_output(monkeypatch):
    _mock_sandbox(monkeypatch)
    result = runner.invoke(cli_app, ["sat", "solve", "--payload", '{"clauses": [[1,2],[-1,2],[1,-2]]}'])
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    body = json.loads(result.stdout)
    assert body["satisfiable"] is True
    assert body["solver"] == "picosat"


def test_cli_linalg_determinant_output_matches_api(monkeypatch):
    _mock_sandbox(monkeypatch)
    # CLI
    cli_result = runner.invoke(cli_app, ["linalg", "determinant", "--payload", '{"matrix": [[1,2],[3,4]]}'])
    assert cli_result.exit_code == 0
    cli_body = json.loads(cli_result.stdout)

    # API
    api_resp = api_client.post("/v1/linalg/determinant", json={"matrix": [[1, 2], [3, 4]]})
    assert api_resp.status_code == 200
    api_body = api_resp.json()

    assert cli_body == api_body, f"CLI {cli_body} != API {api_body}"


def test_cli_invalid_json_input_returns_nonzero_exit_and_clear_error():
    result = runner.invoke(cli_app, ["sat", "solve", "--payload", "not json"])
    assert result.exit_code != 0
    assert "Traceback" not in (result.stdout + result.stderr)


def test_cli_optimize_from_spec_file(monkeypatch, tmp_path):
    _mock_sandbox(monkeypatch)
    spec = {
        "variables": ["x", "y"],
        "objective": {"x": 2, "y": 1},
        "maximize": True,
        "constraints": [
            {"coeffs": {"x": 3, "y": 4}, "max": 2.5},
            {"coeffs": {"x": 1.5, "y": 0.5}, "max": 4, "min": 0.5},
        ],
        "var_types": {"x": "real", "y": "real"},
    }
    spec_file = tmp_path / "problem.json"
    spec_file.write_text(json.dumps(spec))

    result = runner.invoke(cli_app, ["optimize", "milp", "--spec-file", str(spec_file)])
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    body = json.loads(result.stdout)
    assert abs(body["objective_value"] - 1.6666666666666667) < 1e-6


def test_cli_maxima_rejects_injection_like_api(monkeypatch):
    from src.registry import dispatcher as disp
    monkeypatch.setattr(disp, "run_function", lambda *a, **kw: {"ok": False, "result": None, "error": "disallowed token 'system' in expression"})

    result = runner.invoke(cli_app, [
        "maxima", "eval",
        "--payload", '{"expression": "system(\'rm -rf /\')", "operation": "simplify"}',
    ])
    assert result.exit_code != 0
    assert "Traceback" not in (result.stdout + result.stderr)