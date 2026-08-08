import pytest

from src.core.optimize import find_root, minimize, solve_milp

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


@needs_sage
def test_tutorial_reference_case():
    variables = ["x", "y"]
    objective = {"x": 2, "y": 1}
    constraints = [
        {"coeffs": {"x": 3, "y": 4}, "max": 2.5},
        {"coeffs": {"x": 1.5, "y": 0.5}, "max": 4, "min": 0.5},
    ]
    var_types = {"x": "real", "y": "real"}
    result = solve_milp(variables, objective, True, constraints, var_types, nonnegative=True)
    assert result["status"] == "optimal"
    assert abs(result["objective_value"] - 1.6666666666666667) < 1e-6
    assert abs(result["values"]["x"] - 0.8333333333333334) < 1e-6
    assert abs(result["values"]["y"] - 0.0) < 1e-6


@needs_sage
def test_minimization_with_min_and_max_bounds():
    variables = ["x", "y"]
    objective = {"x": 3, "y": 2}
    constraints = [
        {"coeffs": {"x": 5, "y": 7}, "min": 35},
        {"coeffs": {"x": 10, "y": 4}, "min": 40},
    ]
    var_types = {"x": "real", "y": "real"}
    result = solve_milp(variables, objective, False, constraints, var_types, nonnegative=True)
    assert result["status"] == "optimal"
    vals = result["values"]
    # Verify constraints
    assert 5 * vals["x"] + 7 * vals["y"] >= 35 - 1e-9
    assert 10 * vals["x"] + 4 * vals["y"] >= 40 - 1e-9
    # Verify nonnegativity
    assert vals["x"] >= -1e-9
    assert vals["y"] >= -1e-9


@needs_sage
def test_infeasible_problem_returns_infeasible_status():
    variables = ["x"]
    objective = {"x": 1}
    constraints = [
        {"coeffs": {"x": 1}, "max": 1},
        {"coeffs": {"x": 1}, "min": 5},
    ]
    var_types = {"x": "real"}
    result = solve_milp(variables, objective, True, constraints, var_types, nonnegative=True)
    assert result["status"] == "infeasible"
    assert result["values"] is None


@needs_sage
def test_unbounded_problem_returns_unbounded_status():
    variables = ["x"]
    objective = {"x": 1}
    constraints = []
    var_types = {"x": "real"}
    result = solve_milp(variables, objective, True, constraints, var_types, nonnegative=True)
    assert result["status"] == "unbounded"
    assert result["values"] is None


@needs_sage
def test_integer_variable_type_enforced():
    variables = ["x"]
    objective = {"x": 1}
    constraints = [{"coeffs": {"x": 2}, "max": 3}]
    var_types = {"x": "integer"}
    result = solve_milp(variables, objective, True, constraints, var_types, nonnegative=True)
    assert result["status"] == "optimal"
    assert result["values"]["x"] == 1  # 1, not 1.5


@needs_sage
def test_negative_optimal_value():
    """Free real variables with negative optimal value are solved correctly."""
    variables = ["x"]
    objective = {"x": -1}  # minimize -x → maximize x, but with negative obj
    constraints = [
        {"coeffs": {"x": 1}, "max": 10},
        {"coeffs": {"x": 1}, "min": -10},
    ]
    # Without nonnegativity, x can be -10, giving objective -10
    result = solve_milp(variables, objective, False, constraints, {})
    assert result["status"] == "optimal"
    assert result["values"]["x"] == 10  # minimize -x → x=10
    assert abs(result["objective_value"] - (-10)) < 1e-9


@needs_sage
def test_unbounded_returns_proper_status():
    """Unbounded problem returns 'unbounded' status, not 500."""
    variables = ["x"]
    objective = {"x": 1}
    constraints = []
    # No bounds, maximize x → unbounded
    result = solve_milp(variables, objective, True, constraints, {})
    assert result["status"] == "unbounded"
    assert result["values"] is None


def test_unknown_solver_raises():
    with pytest.raises(ValueError, match=r"(?i)solver|glpk|ppl|supported"):
        solve_milp(["x"], {"x": 1}, True, [], solver="not-a-solver")


def test_missing_variable_in_objective_raises():
    with pytest.raises(ValueError, match=r"(?i)not found|undefined|unknown|variable"):
        solve_milp(["x"], {"y": 1}, True, [])


@needs_sage
def test_find_root_linear():
    result = find_root("x - 2", "x", 0, 5)
    assert abs(result - 2.0) < 1e-9


@needs_sage
def test_minimize_quadratic():
    result = minimize("x^2 + y^2", ["x", "y"], [1.0, 1.0])
    assert abs(result[0]) < 1e-6
    assert abs(result[1]) < 1e-6


# ── Expression validation runs before `sage.all` is imported, so these
# injection checks don't require SageMath. ─────────────────────────────────

def test_find_root_rejects_injection_attempt():
    with pytest.raises(ValueError):
        find_root("__import__('os').system('id')", "x", 0, 5)


def test_find_root_rejects_bad_variable_name():
    with pytest.raises(ValueError):
        find_root("x - 2", "x; import os", 0, 5)


def test_minimize_rejects_injection_attempt():
    with pytest.raises(ValueError):
        minimize("__import__('os').system('id')", ["x"], [1.0])


def test_minimize_rejects_bad_variable_name():
    with pytest.raises(ValueError):
        minimize("x^2", ["os"], [1.0])