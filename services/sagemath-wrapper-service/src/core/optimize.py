"""Optimization routines via SageMath — pure functions, no sandbox.

Each function performs SageMath work directly. The dispatcher is responsible
for running these in a subprocess with the configured timeout and limits.
"""

import re

from src.core.expr_safety import validate_identifier, validate_no_dangerous_substrings

# Token whitelist mirroring src.core.maxima's expression grammar: numbers,
# known functions, variable names, operators, whitespace.
_MAX_EXPRESSION_LENGTH = 500
_TOKEN_RE = re.compile(
    r"^(?:"
    r"\d+\.?\d*(?:e[+-]?\d+)?|"
    r"(?:sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|"
    r"exp|log|ln|sqrt|abs|floor|ceil|sign|erf|"
    r"real|imag|conjugate|arctan|arcsin|arccos|arctan2)|"
    r"[a-zA-Z_][a-zA-Z0-9_]*|"
    r"[+\-*/^()\[\],]|"
    r"\s+"
    r")+$",
)


def _validate_expression(expression: str) -> None:
    """Validate that expression contains only whitelisted tokens."""
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError(
            f"expression too long ({len(expression)} > {_MAX_EXPRESSION_LENGTH})"
        )
    if not expression or not expression.strip():
        raise ValueError("expression must not be empty")
    validate_no_dangerous_substrings(expression)
    if not _TOKEN_RE.match(expression):
        raise ValueError("expression contains invalid characters or tokens")


def solve_milp(variables, objective, maximize, constraints, var_types=None, solver="GLPK", nonnegative=None):
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

    # Nonnegativity: default off so free real variables with negative optima
    # are solved correctly.  `nonnegative` may be a bool (apply to all vars)
    # or a set/list/iterable of variable names to force nonnegative.
    if nonnegative is None:
        nonnegative = set()
    elif isinstance(nonnegative, bool):
        nonnegative = set(variables) if nonnegative else set()
    else:
        nonnegative = set(nonnegative)

    from sage.numerical.mip import MixedIntegerLinearProgram

    p = MixedIntegerLinearProgram(maximization=maximize, solver=solver)
    v = p.new_variable(real=True)

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

    # Nonnegativity constraints (only for explicitly-requested variables)
    for var in nonnegative:
        p.add_constraint(v[var] >= 0)

    try:
        obj_val = p.solve()
    except Exception as e:
        # Robust status detection: inspect the SageCythonException's
        # underlying MIPSolverException type where possible.
        if hasattr(e, "args") and e.args:
            inner = e.args[0]
            # MIPSolverException carries a .type attribute like 'infeasible'
            # or 'unbounded'.
            exc_type = getattr(inner, "type", None)
            if exc_type is not None:
                exc_type = str(exc_type).lower()
                if "infeas" in exc_type or "no feasible" in exc_type:
                    return {"status": "infeasible", "objective_value": None, "values": None}
                if "unbound" in exc_type:
                    return {"status": "unbounded", "objective_value": None, "values": None}
        # Last-resort fallback: string matching
        msg = str(e).lower()
        if "infeasible" in msg or "no feasible" in msg:
            return {"status": "infeasible", "objective_value": None, "values": None}
        if "unbounded" in msg or "unbound" in msg:
            return {"status": "unbounded", "objective_value": None, "values": None}
        raise

    vals = p.get_values(v)
    return {
        "status": "optimal",
        "objective_value": float(obj_val),
        "values": {var: float(vals[var]) for var in variables},
    }


def find_root(expression, variable, a, b):
    """Find root of expression in interval [a, b]."""
    _validate_expression(expression)
    validate_identifier(variable, "variable")

    from sage.all import SR, var
    from sage.all import find_root as sage_find_root
    v = var(variable)
    f = SR(expression)
    return float(sage_find_root(f, a, b, v))


def minimize(expression, variables, x0):
    """Unconstrained minimization of expression using Nelder-Mead.

    *variables* determines the variable order and must match *x0* in length.
    """
    _validate_expression(expression)
    for name in variables:
        validate_identifier(name, "variable")
    if len(variables) != len(x0):
        raise ValueError(
            f"variables count ({len(variables)}) must match x0 length ({len(x0)})"
        )
    from sage.all import SR
    f = SR(expression)
    from sage.numerical.optimize import minimize as sage_minimize
    sol = sage_minimize(f, x0, gradient=None, algorithm='default')
    return [float(s) for s in sol]