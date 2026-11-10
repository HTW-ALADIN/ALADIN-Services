"""Linear algebra operations via SageMath — pure functions, no sandbox.

Each function performs SageMath work directly. The dispatcher is responsible
for running these in a subprocess with the configured timeout and limits.
"""

import re

from src.core.expr_safety import validate_identifier, validate_no_dangerous_substrings

# Matrix-algebra expressions may reference declared matrix/vector names,
# numbers, a small allowlist of methods/attributes, and arithmetic operators.
# Anything else (including dunder attribute access) is rejected.
_MAX_EXPRESSION_LENGTH = 1000
_ALLOWED_METHODS = frozenset({
    "inverse", "transpose", "det", "rank", "charpoly", "echelon_form",
    "kernel", "right_kernel", "left_kernel", "eigenvalues",
    "eigenvectors_left", "eigenvectors_right", "exp", "LU", "QR",
    "cholesky", "SVD", "T", "trace", "norm", "adjugate", "rows", "columns",
    "list",
})
# NOTE: matched token-by-token at an advancing offset (see
# ``_validate_matrix_expression``), never wrapped in an outer ``(?:...)+``
# group — combining these overlapping alternatives under a single repeated
# group is vulnerable to catastrophic backtracking (ReDoS) on crafted
# non-matching input. Do not reintroduce that shape.
_EXPR_TOKEN_RE = re.compile(
    r"\d+\.?\d*(?:e[+-]?\d+)?"
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|[+\-*/^().,]"
    r"|\s+",
)
# Matches a dotted attribute/method access, tolerating optional whitespace
# between the ``.`` and the identifier (Python itself accepts `A. gap()` as
# `A.gap()`) so the allowlist below cannot be bypassed by inserting spaces.
_DOTTED_METHOD_RE = re.compile(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)")


def _validate_square(matrix, name):
    """Ensure matrix is a non-empty square list-of-lists."""
    n = len(matrix)
    if n == 0:
        raise ValueError(f"{name}: matrix must be non-empty")
    for row in matrix:
        if len(row) != n:
            raise ValueError(f"{name}: non-square matrix, got {len(matrix)}x{len(row)}")


def _sage_matrix(matrix):
    """Build a SageMath RDF matrix from a list-of-lists."""
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    return sage_matrix(RDF, matrix)


def _to_rows(m):
    """Convert a SageMath matrix to a list-of-lists of floats."""
    return [[float(m[i][j]) for j in range(m.ncols())] for i in range(m.nrows())]


def determinant(matrix):
    _validate_square(matrix, "determinant")
    return float(_sage_matrix(matrix).determinant())


def inverse(matrix):
    _validate_square(matrix, "inverse")
    m = _sage_matrix(matrix)
    try:
        inv = m.inverse()
    except (ZeroDivisionError, ValueError):
        raise ValueError("singular matrix: not invertible")
    return _to_rows(inv)


def solve_linear_system(a, b):
    _validate_square(a, "solve_linear_system")
    if len(a) != len(b):
        raise ValueError("solve_linear_system: a and b dimension mismatch")
    from sage.all import RDF, vector
    m = _sage_matrix(a)
    v = vector(RDF, b)
    try:
        sol = m.solve_right(v)
    except (ValueError, ZeroDivisionError):
        raise ValueError("no solution: inconsistent system")
    return [float(sol[i]) for i in range(len(sol))]


def qr(matrix):
    _validate_square(matrix, "qr")
    q, r = _sage_matrix(matrix).QR()
    return {"Q": _to_rows(q), "R": _to_rows(r)}


def lu(matrix):
    _validate_square(matrix, "lu")
    p, l, u = _sage_matrix(matrix).LU()
    return {"P": _to_rows(p), "L": _to_rows(l), "U": _to_rows(u)}


def cholesky(matrix):
    _validate_square(matrix, "cholesky")
    return _to_rows(_sage_matrix(matrix).cholesky())


def svd(matrix):
    """Singular value decomposition. Accepts non-square matrices."""
    u, s, v = _sage_matrix(matrix).SVD()
    return {
        "U": _to_rows(u),
        "Sigma": [float(s[i]) for i in range(len(s))],
        "V": _to_rows(v),
    }


def matrix_exp(matrix):
    _validate_square(matrix, "matrix_exp")
    return _to_rows(_sage_matrix(matrix).exp())


def right_kernel(matrix):
    _validate_square(matrix, "right_kernel")
    return _to_rows(_sage_matrix(matrix).right_kernel().basis_matrix())


def left_kernel(matrix):
    _validate_square(matrix, "left_kernel")
    return _to_rows(_sage_matrix(matrix).left_kernel().basis_matrix())


def charpoly(matrix):
    _validate_square(matrix, "charpoly")
    return str(_sage_matrix(matrix).charpoly("x"))


def _validate_matrix_expression(expression: str) -> None:
    """Validate a matrix-algebra expression before it is evaluated.

    Only declared identifiers, numbers, arithmetic operators, and an
    explicit allowlist of matrix/vector methods are permitted. Dunder
    attribute access and any dangerous substring (import, exec, eval, ...)
    are rejected outright.
    """
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError(
            f"expression too long ({len(expression)} > {_MAX_EXPRESSION_LENGTH})"
        )
    if not expression or not expression.strip():
        raise ValueError("expression must not be empty")
    validate_no_dangerous_substrings(expression)
    pos = 0
    length = len(expression)
    while pos < length:
        match = _EXPR_TOKEN_RE.match(expression, pos)
        if not match:
            raise ValueError("expression contains invalid characters or tokens")
        pos = match.end()
    for method in _DOTTED_METHOD_RE.findall(expression):
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"method '{method}' is not allowed in expression")


def evaluate_expression(expression, matrices=None, vectors=None):
    """Evaluate a matrix-algebra *expression* against named matrices/vectors.

    *matrices* and *vectors* are ``{name: data}`` mappings used to build
    SageMath ``Matrix``/``vector`` objects bound to *expression*'s
    namespace. The expression is validated (allowlisted methods only, no
    dunder attribute access, no dangerous substrings) and evaluated with an
    empty ``__builtins__`` so no Python builtin (``__import__``, ``open``,
    ``exec``, ...) is reachable even if validation is bypassed.
    """
    matrices = matrices or {}
    vectors = vectors or {}

    for name in (*matrices.keys(), *vectors.keys()):
        validate_identifier(name, "matrix/vector name")
    _validate_matrix_expression(expression)

    from sage.all import RDF, vector
    from sage.all import matrix as sage_matrix

    namespace = {}
    for name, data in matrices.items():
        namespace[name] = sage_matrix(RDF, data)
    for name, data in vectors.items():
        namespace[name] = vector(RDF, data)

    # `_validate_matrix_expression` guarantees `^` is only ever tokenized as
    # a standalone operator character (never part of a number/identifier),
    # so it is safe to translate Sage/Maxima-style `^` (power) into Python's
    # `**` here — plain `eval()` would otherwise treat `^` as bitwise XOR,
    # which Sage matrix/vector objects don't support.
    python_expression = expression.replace("^", "**")

    try:
        result = eval(python_expression, {"__builtins__": {}}, namespace)
    except Exception as exc:
        raise ValueError(f"failed to evaluate expression: {exc}") from exc

    try:
        return [list(row) for row in result.rows()]
    except AttributeError:
        try:
            return list(result)
        except TypeError:
            return result