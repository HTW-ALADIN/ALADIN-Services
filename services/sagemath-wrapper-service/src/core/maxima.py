"""Maxima integration via SageMath — pure functions, no sandbox.

Each function performs SageMath work directly. The dispatcher is responsible
for running these in a subprocess with the configured timeout and limits.
"""

import re

from src.core.expr_safety import validate_no_dangerous_substrings

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
    validate_no_dangerous_substrings(expression)
    if not _TOKEN_RE.match(expression):
        raise ValueError("expression contains invalid characters or tokens")


def evaluate(expression, operation, variable="x", bounds=None):
    """Evaluate a symbolic expression using one of the allowed operations."""
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(f"unknown operation '{operation}'. allowed: {', '.join(_ALLOWED_OPERATIONS)}")

    _validate_expression(expression)

    if bounds is not None and len(bounds) != 2:
        raise ValueError("bounds must be a tuple/list of length 2")

    from sage.all import SR, var

    v = var(variable)
    expr = SR(expression)

    if operation == "simplify":
        return str(expr.simplify_full())

    if operation == "differentiate":
        return str(expr.diff(v))

    if operation == "integrate":
        if bounds is not None:
            return float(expr.integrate(v, bounds[0], bounds[1]))
        integral = expr.integrate(v)
        return {"result": str(integral), "simplify": str(integral.simplify_full())}

    if operation == "solve":
        sol = SR(expression).solve(v)
        return [str(s) for s in sol]

    if operation == "limit":
        if bounds is None:
            raise ValueError("bounds is required for operation 'limit'")
        from sage.all import limit
        return str(limit(expr, v, bounds[0]))

    if operation == "series":
        if bounds is None:
            raise ValueError("bounds is required for operation 'series'")
        from sage.all import series
        n = int(bounds[1]) if len(bounds) > 1 else 6
        return str(series(expr, v, bounds[0], n))

    if operation == "laplace":
        from sage.all import laplace
        return str(laplace(expr, v, var("s")))

    raise ValueError(f"unknown operation '{operation}'")