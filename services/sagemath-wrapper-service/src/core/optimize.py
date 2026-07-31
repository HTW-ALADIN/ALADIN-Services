"""Optimization routines via SageMath, sandboxed via run_sandboxed."""

import src.sandbox.executor as _executor


def solve_milp(variables, objective, maximize, constraints, var_types=None, solver="GLPK"):
    if solver not in ("GLPK", "PPL", "CBC", "InteractiveLP", "CPLEX", "CVXOPT"):
        raise ValueError(f"unsupported solver '{solver}'. supported: GLPK, PPL, CBC, InteractiveLP, CPLEX, CVXOPT")

    var_set = set(variables)
    for var in objective:
        if var not in var_set:
            raise ValueError(f"unknown variable '{var}' in objective (not in variables list)")

    var_types = (var_types or {})
    for var, typ in var_types.items():
        if var not in var_set:
            raise ValueError(f"unknown variable '{var}' in var_types")
        if typ not in ("real", "integer"):
            raise ValueError(f"invalid var_type '{typ}' for '{var}'")

    for c in constraints:
        for var in c.get("coeffs", {}):
            if var not in var_set:
                raise ValueError(f"unknown variable '{var}' in constraint")

    result = _executor.run_sandboxed(
        _milp_inner, {
            "variables": variables, "objective": objective,
            "maximize": maximize, "constraints": constraints,
            "var_types": var_types, "solver": solver,
        },
    )
    if not result["ok"]:
        return {"status": "error", "objective_value": None, "values": None, "error": result["error"]}
    return result["result"]


def find_root(expression, variable, a, b):
    """Find root of expression in interval [a, b]."""
    result = _executor.run_sandboxed(
        _find_root_inner, {"expression": expression, "variable": variable, "a": a, "b": b}
    )
    if not result["ok"]:
        return {"result": None, "error": result["error"]}
    return result["result"]


def minimize(expression, variables, x0):
    """Unconstrained minimization of expression using Nelder-Mead."""
    result = _executor.run_sandboxed(
        _minimize_inner, {"expression": expression, "variables": variables, "x0": x0}
    )
    if not result["ok"]:
        return {"result": None, "error": result["error"]}
    return result["result"]


def _milp_inner(variables, objective, maximize, constraints, var_types, solver):
    from sage.numerical.mip import MixedIntegerLinearProgram

    p = MixedIntegerLinearProgram(maximization=maximize, solver=solver)
    v = p.new_variable(real=True, nonnegative=True)

    # Set objective
    expr = sum(objective[var] * v[var] for var in objective)
    p.set_objective(expr)

    # Add constraints
    for c in constraints:
        coeffs = c.get("coeffs", {})
        expr = sum(coeffs[var] * v[var] for var in coeffs)
        if "max" in c:
            p.add_constraint(expr, max=c["max"])
        if "min" in c:
            p.add_constraint(expr, min=c["min"])

    # Integer constraints
    for var, typ in var_types.items():
        if typ == "integer":
            p.set_integer(v[var])

    try:
        obj_val = p.solve()
    except Exception as e:  # noqa: BLE001 — caught at sandbox boundary
        msg = str(e).lower()
        if "infeasible" in msg or "no feasible" in msg:
            return {"status": "infeasible", "objective_value": None, "values": None}
        if "unbounded" in msg:
            return {"status": "unbounded", "objective_value": None, "values": None}
        return {"status": "error", "objective_value": None, "values": None, "error": str(e)}

    vals = p.get_values(v)
    return {
        "status": "optimal",
        "objective_value": float(obj_val),
        "values": {var: float(vals[var]) for var in variables},
    }


def _find_root_inner(expression, variable, a, b):
    from sage.all import SR, find_root, var
    v = var(variable)
    f = SR(expression)
    return {"result": float(find_root(f, a, b, v)), "error": None}


def _minimize_inner(expression, variables, x0):
    from sage.all import SR
    f = SR(expression)
    from sage.numerical.optimize import minimize as sage_minimize
    sol = sage_minimize(f, x0, gradient=None, algorithm='default')
    return {"result": [float(s) for s in sol], "error": None}