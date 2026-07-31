import pytest

from src.core.sat import solve_cnf

_has_sage = False
try:
    import sage.all  # noqa: F401
    _has_sage = True
except ImportError:
    pass

needs_sage = pytest.mark.skipif(
    not _has_sage,
    reason="requires SageMath (not available in this environment)",
)


def verify_assignment(clauses, assignment):
    """Prüft, ob assignment alle Klauseln erfüllt."""
    for clause in clauses:
        if not any(
            (lit > 0 and assignment.get(str(abs(lit)), False))
            or (lit < 0 and not assignment.get(str(abs(lit)), True))
            for lit in clause
        ):
            return False
    return True


@needs_sage
def test_simple_satisfiable_formula():
    clauses = [[1, 2], [-1, 2], [1, -2]]
    result = solve_cnf(clauses)
    assert result["satisfiable"] is True
    assert result["solver"] == "picosat"
    assert verify_assignment(clauses, result["assignment"])


@needs_sage
def test_unsatisfiable_formula():
    clauses = [[1, 2], [-1, 2], [1, -2], [-1, -2]]
    result = solve_cnf(clauses)
    assert result["satisfiable"] is False
    assert result["assignment"] is None


@needs_sage
def test_single_variable_true():
    clauses = [[1]]
    result = solve_cnf(clauses)
    assert result["satisfiable"] is True
    assert result["assignment"]["1"] is True


@needs_sage
def test_empty_clause_is_unsatisfiable():
    clauses = [[]]
    result = solve_cnf(clauses)
    assert result["satisfiable"] is False


def test_invalid_variable_index_zero_raises():
    with pytest.raises(ValueError, match=r"(?i)index|zero"):
        solve_cnf([[0, 1]])


def test_unknown_solver_name_raises():
    with pytest.raises(ValueError, match=r"(?i)solver|picosat|supported"):
        solve_cnf([[1]], solver="not-a-real-solver")


@pytest.mark.integration
def test_result_runs_inside_sandbox(monkeypatch):
    called = False

    def mock_run_sandboxed(fn, args, timeout_s=5.0):
        nonlocal called
        called = True
        return {"ok": True, "result": {"satisfiable": True, "assignment": {"1": True}, "solver": "picosat"}, "error": None}

    import src.sandbox.executor as exec_mod
    monkeypatch.setattr(exec_mod, "run_sandboxed", mock_run_sandboxed)

    result = solve_cnf([[1]])
    assert called, "solve_cnf hat run_sandboxed nicht aufgerufen"
    assert result["satisfiable"] is True