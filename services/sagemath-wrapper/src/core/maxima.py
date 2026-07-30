"""Maxima integration via SageMath, sandboxed via run_sandboxed."""

import re

import src.sandbox.executor as _executor

_ALLOWED_OPERATIONS = ("simplify", "differentiate", "integrate", "solve", "limit", "series", "laplace")

# Token whitelist: numbers, known functions, variable names, operators, whitespace
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
    if len(expression) > 500:
        raise ValueError(f"expression too long ({len(expression)} > 500)")
    if not expression or not expression.strip():
        raise ValueError("expression must not be empty")
    lower = expression.lower()
    for bad in ("system", "openr", "openw", "load", "os.", "eval", "exec",
                "__import__", "subprocess", "import", "compile", "execfile"):
        if bad in lower:
            raise ValueError(f"disallowed token '{bad}' in expression")
    if not _TOKEN_RE.match(expression):
        raise ValueError("expression contains invalid characters or tokens")


_ALLOWED_OPERATIONS = ("simplify", "differentiate", "integrate", "solve", "limit", "series", "laplace")


def evaluate(expression, operation, variable="x", bounds=None):
    """Evaluate a symbolic expression using one of the allowed operations."""
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(f"unknown operation '{operation}'. allowed: {', '.join(_ALLOWED_OPERATIONS)}")

    _validate_expression(expression)

    if bounds is not None and len(bounds) != 2:
        raise ValueError("bounds must be a tuple/list of length 2")

    result = _executor.run_sandboxed(
        _evaluate_inner,
        {"expression": expression, "operation": operation, "variable": variable, "bounds": bounds},
        timeout_s=3.0,
    )
    if not result["ok"]:
        return {"result": None, "error": result["error"]}
    return result["result"]


def _evaluate_inner(expression, operation, variable, bounds):
    """Run inside sandbox child process — SageMath imports here."""
    from sage.all import SR, var

    v = var(variable)
    expr = SR(expression)

    if operation == "simplify":
        return {"result": str(expr.simplify_full()), "error": None}

    if operation == "differentiate":
        return {"result": str(expr.diff(v)), "error": None}

    if operation == "integrate":
        if bounds is not None:
            return {"result": float(expr.integrate(v, bounds[0], bounds[1])), "error": None}
        integral = expr.integrate(v)
        return {"result": str(integral), "simplify": str(integral.simplify_full()), "error": None}

    if operation == "solve":
        sol = SR(expression).solve(v)
        return {"result": [str(s) for s in sol], "error": None}

    if operation == "limit":
        from sage.all import limit
        return {"result": str(limit(expr, v, bounds[0])), "error": None}

    if operation == "series":
        from sage.all import series
        n = int(bounds[1]) if bounds and len(bounds) > 1 else 6
        return {"result": str(series(expr, v, bounds[0], n)), "error": None}

    if operation == "laplace":
        from sage.all import laplace
        return {"result": str(laplace(expr, v, var("s"))), "error": None}

    return {"result": None, "error": f"unknown operation '{operation}'"}

    if operation == "integrate":
        if bounds is not None:
            return {"result": float(expr.integrate(v, bounds[0], bounds[1])), "error": None}
        integral = expr.integrate(v)
        return {"result": str(integral), "simplify": str(integral.simplify_full()), "error": None}

    return {"result": None, "error": f"unknown operation '{operation}'"}