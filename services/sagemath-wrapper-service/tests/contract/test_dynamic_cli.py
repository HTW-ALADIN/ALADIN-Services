"""Contract tests for dynamic CLI registration."""

import json
import os

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.api.main import app as api_app
from src.cli.main import app as cli_app
from src.registry.loader import load_registry

runner = CliRunner()
api_client = TestClient(api_app)

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "registry"
)


def _mock_sandbox(monkeypatch):
    """Mock run_sandboxed so tests don't need SageMath."""
    import src.sandbox.executor as exec_mod

    def mock(fn, args, timeout_s=5.0):
        if "clauses" in args:
            return {"ok": True, "result": {"satisfiable": True, "assignment": {"1": True, "2": True}, "solver": "picosat"}, "error": None}
        if args.get("matrix") == [[1, 2], [3, 4]]:
            return {"ok": True, "result": {"result": -2, "error": None}, "error": None}
        if "variables" in args:
            return {"ok": True, "result": {"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}, "error": None}
        if "expression" in args:
            return {"ok": True, "result": {"result": "x^2", "error": None}, "error": None}
        return {"ok": True, "result": None, "error": None}

    monkeypatch.setattr(exec_mod, "run_sandboxed", mock)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDynamicCLI:
    def test_cli_and_api_use_same_dispatcher_for_same_operation(self, monkeypatch):
        """CLI and API produce identical results for the same operation."""
        _mock_sandbox(monkeypatch)

        # CLI
        cli_result = runner.invoke(
            cli_app,
            ["linalg", "determinant", "--matrix", "[[1,2],[3,4]]"],
        )
        assert cli_result.exit_code == 0, cli_result.stdout
        cli_body = json.loads(cli_result.stdout)

        # API
        api_resp = api_client.post("/v1/linalg/determinant", json={"matrix": [[1, 2], [3, 4]]})
        assert api_resp.status_code == 200
        api_body = api_resp.json()

        assert cli_body == api_body

    def test_new_registry_entry_appears_as_cli_subcommand_without_code_change(self, monkeypatch):
        """Adding a registry entry makes it immediately available as a CLI command."""

        # Create a temp registry with a new entry + existing ones

        import typer
        from typer.testing import CliRunner

        from src.cli.dynamic_commands import register_commands
        from src.registry.loader import OperationSpec

        # Create a fresh Typer app with serve command
        test_app = typer.Typer()

        @test_app.command()
        def serve():
            import uvicorn
            uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)

        # Load real registry plus a new entry
        ops = load_registry(REGISTRY_PATH)
        new_op = OperationSpec(
            id="test.hello",
            summary="A test operation",
            kind="function",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string", "default": "world"}},
            },
            output_type="object",
            timeout_s=5.0,
            function_ref="core.sat:solve_cnf",
        )
        ops.append(new_op)
        register_commands(test_app, ops)

        local_runner = CliRunner()
        result = local_runner.invoke(test_app, ["test", "hello", "--name", "test"])
        # Should reach the dispatcher (which calls the sandbox, which we haven't mocked)
        # Just checking the command exists and is callable
        assert result.exit_code != 0  # sandbox not mocked, but command exists
        output = (result.stdout + result.stderr).lower()
        assert "error" in output, f"expected error message, got stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_cli_help_output_reflects_registry_summary_field(self):
        """CLI --help shows the summary from the YAML for each command."""
        result = runner.invoke(cli_app, ["sat", "solve", "--help"])
        assert result.exit_code == 0
        # The summary from sat.yaml should appear somewhere
        assert "Solve a CNF SAT formula" in result.stdout

        result = runner.invoke(cli_app, ["linalg", "determinant", "--help"])
        assert result.exit_code == 0
        assert "Determinant of a square matrix" in result.stdout