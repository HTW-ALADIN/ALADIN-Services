"""Linear algebra operations via SageMath — pure functions, no sandbox.

Each function performs SageMath work directly. The dispatcher is responsible
for running these in a subprocess with the configured timeout and limits.
"""


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
    return _to_rows(_sage_matrix(matrix).right_kernel())


def left_kernel(matrix):
    _validate_square(matrix, "left_kernel")
    return _to_rows(_sage_matrix(matrix).left_kernel())


def charpoly(matrix):
    _validate_square(matrix, "charpoly")
    return str(_sage_matrix(matrix).charpoly("x"))