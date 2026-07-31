"""Linear algebra operations via SageMath, sandboxed via run_sandboxed."""

import src.sandbox.executor as _executor


def _validate_square(matrix, name):
    """Ensure matrix is a non-empty square list-of-lists."""
    n = len(matrix)
    if n == 0:
        raise ValueError(f"{name}: matrix must be non-empty")
    for row in matrix:
        if len(row) != n:
            raise ValueError(f"{name}: non-square matrix, got {len(matrix)}x{len(row)}")


def determinant(matrix):
    _validate_square(matrix, "determinant")
    return _unwrap(_executor.run_sandboxed(_det_inner, {"matrix": matrix}))


def inverse(matrix):
    _validate_square(matrix, "inverse")
    return _unwrap(_executor.run_sandboxed(_inv_inner, {"matrix": matrix}))


def eigenvalues(matrix):
    _validate_square(matrix, "eigenvalues")
    return _unwrap(_executor.run_sandboxed(_eig_inner, {"matrix": matrix}))


def solve_linear_system(a, b):
    _validate_square(a, "solve_linear_system")
    if len(a) != len(b):
        raise ValueError("solve_linear_system: a and b dimension mismatch")
    return _unwrap(_executor.run_sandboxed(_solve_inner, {"a": a, "b": b}))


def qr(matrix):
    _validate_square(matrix, "qr")
    return _unwrap(_executor.run_sandboxed(_qr_inner, {"matrix": matrix}))


def lu(matrix):
    _validate_square(matrix, "lu")
    return _unwrap(_executor.run_sandboxed(_lu_inner, {"matrix": matrix}))


def cholesky(matrix):
    _validate_square(matrix, "cholesky")
    return _unwrap(_executor.run_sandboxed(_cholesky_inner, {"matrix": matrix}))


def svd(matrix):
    return _unwrap(_executor.run_sandboxed(_svd_inner, {"matrix": matrix}))


def matrix_exp(matrix):
    _validate_square(matrix, "matrix_exp")
    return _unwrap(_executor.run_sandboxed(_exp_inner, {"matrix": matrix}))


def right_kernel(matrix):
    _validate_square(matrix, "right_kernel")
    return _unwrap(_executor.run_sandboxed(_rk_inner, {"matrix": matrix}))


def left_kernel(matrix):
    _validate_square(matrix, "left_kernel")
    return _unwrap(_executor.run_sandboxed(_lk_inner, {"matrix": matrix}))


def charpoly(matrix):
    _validate_square(matrix, "charpoly")
    return _unwrap(_executor.run_sandboxed(_charpoly_inner, {"matrix": matrix}))


def _unwrap(result):
    if not result["ok"]:
        return {"result": None, "error": result["error"]}
    return result["result"]


def _det_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    return {"result": float(m.determinant()), "error": None}


def _inv_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    try:
        inv = m.inverse()
    except (ZeroDivisionError, ValueError):
        return {"result": None, "error": "singular matrix: not invertible"}
    return {"result": [[float(inv[i][j]) for j in range(inv.ncols())] for i in range(inv.nrows())], "error": None}


def _eig_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    ev = m.eigenvalues()
    return {"result": [float(v) for v in ev], "error": None}


def _solve_inner(a, b):
    from sage.all import RDF, vector
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, a)
    v = vector(RDF, b)
    try:
        sol = m.solve_right(v)
    except (ValueError, ZeroDivisionError):
        return {"result": None, "error": "no solution: inconsistent system"}
    return {"result": [float(sol[i]) for i in range(len(sol))], "error": None}


def _qr_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    q, r = m.QR()
    return {"result": {"Q": [[float(q[i][j]) for j in range(q.ncols())] for i in range(q.nrows())],
                       "R": [[float(r[i][j]) for j in range(r.ncols())] for i in range(r.nrows())]}, "error": None}


def _lu_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    p, l, u = m.LU()
    return {"result": {"P": [[float(p[i][j]) for j in range(p.ncols())] for i in range(p.nrows())],
                       "L": [[float(l[i][j]) for j in range(l.ncols())] for i in range(l.nrows())],
                       "U": [[float(u[i][j]) for j in range(u.ncols())] for i in range(u.nrows())]}, "error": None}


def _cholesky_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    c = m.cholesky()
    return {"result": [[float(c[i][j]) for j in range(c.ncols())] for i in range(c.nrows())], "error": None}


def _svd_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    u, s, v = m.SVD()
    return {"result": {"U": [[float(u[i][j]) for j in range(u.ncols())] for i in range(u.nrows())],
                       "Sigma": [float(s[i]) for i in range(len(s))],
                       "V": [[float(v[i][j]) for j in range(v.ncols())] for i in range(v.nrows())]}, "error": None}


def _exp_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    e = m.exp()
    return {"result": [[float(e[i][j]) for j in range(e.ncols())] for i in range(e.nrows())], "error": None}


def _rk_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    k = m.right_kernel()
    return {"result": [[float(k[i][j]) for j in range(k.ncols())] for i in range(k.nrows())], "error": None}


def _lk_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    k = m.left_kernel()
    return {"result": [[float(k[i][j]) for j in range(k.ncols())] for i in range(k.nrows())], "error": None}


def _charpoly_inner(matrix):
    from sage.all import RDF
    from sage.all import matrix as sage_matrix
    m = sage_matrix(RDF, matrix)
    return {"result": str(m.charpoly("x")), "error": None}