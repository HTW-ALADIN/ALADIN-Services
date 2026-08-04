import pytest

from src.core.linalg import (
    charpoly,
    cholesky,
    determinant,
    inverse,
    left_kernel,
    lu,
    matrix_exp,
    qr,
    right_kernel,
    solve_linear_system,
    svd,
)

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
def test_determinant_2x2():
    result = determinant([[1, 2], [3, 4]])
    assert result == -2


@needs_sage
def test_determinant_singular_matrix_is_zero():
    result = determinant([[1, 2], [2, 4]])
    assert result == 0


@needs_sage
def test_inverse_identity_roundtrip():
    m = [[2, 0], [0, 2]]
    inv = inverse(m)
    for row in inv:
        assert len(row) == 2
    n = len(m)
    product = [[sum(m[i][k] * inv[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            expected = 1.0 if i == j else 0.0
            assert abs(product[i][j] - expected) < 1e-9


@needs_sage
def test_inverse_singular_matrix_returns_error():
    with pytest.raises(ValueError, match=r"(?i)singular|invertible"):
        inverse([[1, 2], [2, 4]])


@needs_sage
def test_solve_linear_system_unique_solution():
    a = [[2, 1], [1, 3]]
    b = [5, 10]
    x = solve_linear_system(a, b)
    assert len(x) == 2
    assert abs(x[0] - 1) < 1e-9
    assert abs(x[1] - 3) < 1e-9


@needs_sage
def test_solve_linear_system_no_solution_returns_error():
    with pytest.raises(ValueError, match=r"(?i)no solution|inconsistent"):
        solve_linear_system([[1, 1], [1, 1]], [1, 2])


def test_non_square_matrix_for_determinant_raises():
    with pytest.raises(ValueError, match=r"(?i)square"):
        determinant([[1, 2, 3], [4, 5, 6]])


@needs_sage
def test_qr_roundtrip():
    m = [[1, 2], [3, 4]]
    r = qr(m)
    assert "Q" in r and "R" in r
    n = len(m)
    product = [[sum(r["Q"][i][k] * r["R"][k][j] for k in range(n)) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            assert abs(product[i][j] - m[i][j]) < 1e-9


@needs_sage
def test_lu_decomposition():
    m = [[4, 3], [6, 3]]
    r = lu(m)
    assert all(k in r for k in ("P", "L", "U"))


@needs_sage
def test_cholesky_roundtrip():
    m = [[4, 2], [2, 3]]
    c = cholesky(m)
    n = len(m)
    product = [[sum(c[i][k] * c[j][k] for k in range(n)) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            assert abs(product[i][j] - m[i][j]) < 1e-9


@needs_sage
def test_svd_shapes():
    r = svd([[1, 2, 3], [4, 5, 6]])
    assert all(k in r for k in ("U", "Sigma", "V"))


@needs_sage
def test_matrix_exp_2x2():
    result = matrix_exp([[1, 0], [0, 1]])
    assert abs(result[0][0] - 2.718281828) < 1e-6
    assert abs(result[1][1] - 2.718281828) < 1e-6


@needs_sage
def test_right_kernel():
    result = right_kernel([[1, 2], [2, 4]])
    assert len(result) > 0  # singular → non-trivial kernel


@needs_sage
def test_left_kernel():
    result = left_kernel([[1, 2], [2, 4]])
    assert len(result) > 0


@needs_sage
def test_charpoly_2x2():
    result = charpoly([[1, 2], [3, 4]])
    assert "x" in result


def test_non_square_matrix_for_lu_raises():
    with pytest.raises(ValueError, match=r"(?i)square"):
        lu([[1, 2, 3], [4, 5, 6]])


def test_non_square_matrix_for_cholesky_raises():
    with pytest.raises(ValueError, match=r"(?i)square"):
        cholesky([[1, 2, 3], [4, 5, 6]])


def test_non_square_matrix_for_exp_raises():
    with pytest.raises(ValueError, match=r"(?i)square"):
        matrix_exp([[1, 2, 3], [4, 5, 6]])


def test_non_square_matrix_for_charpoly_raises():
    with pytest.raises(ValueError, match=r"(?i)square"):
        charpoly([[1, 2, 3], [4, 5, 6]])