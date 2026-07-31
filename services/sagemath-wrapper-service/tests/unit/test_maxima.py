import pytest

from src.core.maxima import _validate_expression, evaluate

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


# ── _validate_expression unit tests ──────────────────────────────────────────

def test_validate_accepts_simple_polynomial():
    _validate_expression("x^2 + 2*x + 1")


def test_validate_accepts_trigonometric_expression():
    _validate_expression("sin(x)^2 + cos(x)^2")


def test_validate_accepts_exponential_and_log():
    _validate_expression("exp(x) + log(y) + sqrt(z)")


def test_validate_accepts_numeric_constants():
    _validate_expression("3.14 * x + 2")


def test_validate_rejects_system_call():
    with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
        _validate_expression("system('rm -rf /')")


def test_validate_rejects_file_io_keywords():
    for bad in ("openr", "load", "system", "os."):
        with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
            _validate_expression(bad)


def test_validate_rejects_too_long_expression():
    with pytest.raises(ValueError, match=r"(?i)too long|length|500"):
        _validate_expression("x" * 501)


def test_validate_rejects_semicolon_or_colon():
    with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
        _validate_expression("x; system('rm')")
    with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
        _validate_expression("x: 5")


# ── evaluate integration tests ───────────────────────────────────────────────

@needs_sage
def test_simplify_basic_expression():
    result = evaluate("x^2 + 2*x + 1", "simplify")
    assert result["error"] is None
    from sage.all import SR
    original = SR("x^2 + 2*x + 1")
    simplified = SR(result["result"])
    assert abs(float(simplified.subs(x=3)) - float(original.subs(x=3))) < 1e-9


@needs_sage
def test_differentiate_polynomial():
    result = evaluate("x^3", "differentiate", variable="x")
    assert result["error"] is None
    from sage.all import SR
    deriv = SR(result["result"])
    expected = SR("3*x^2")
    for xv in (0, 1, 2, 5):
        assert abs(float(deriv.subs(x=xv)) - float(expected.subs(x=xv))) < 1e-9


@needs_sage
def test_integrate_indefinite():
    result = evaluate("2*x", "integrate", variable="x")
    assert result["error"] is None
    from sage.all import SR, var
    x = var("x")
    integral = SR(result["result"])
    deriv = integral.diff(x)
    original = SR("2*x")
    for xv in (0, 1, 2, 5):
        assert abs(float(deriv.subs(x=xv)) - float(original.subs(x=xv))) < 1e-9


@needs_sage
def test_integrate_definite_with_bounds():
    result = evaluate("x", "integrate", variable="x", bounds=(0, 2))
    assert result["error"] is None
    assert abs(float(result["result"]) - 2.0) < 1e-9


@needs_sage
def test_solve_equation():
    result = evaluate("x^2 - 4", "solve", variable="x")
    assert result["error"] is None
    sols = [str(s) for s in result["result"]]
    assert any("2" in s for s in sols)
    assert any("-2" in s for s in sols)


@needs_sage
def test_limit_at_infinity():
    result = evaluate("1/x", "limit", variable="x", bounds=(float("inf"),))
    assert result["error"] is None
    assert "0" in str(result["result"])


@needs_sage
def test_series_expansion():
    result = evaluate("sin(x)", "series", variable="x", bounds=(0, 5))
    assert result["error"] is None
    assert "x" in str(result["result"])


@needs_sage
def test_laplace_transform():
    result = evaluate("t", "laplace", variable="t")
    assert result["error"] is None
    assert "s" in str(result["result"])


def test_rejects_expression_with_disallowed_tokens(monkeypatch):
    import src.sandbox.executor as exec_mod
    calls = []
    monkeypatch.setattr(exec_mod, "run_sandboxed", lambda *a, **kw: calls.append(1) or {"ok": True, "result": None, "error": None})

    with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
        evaluate("system('rm -rf /')", "simplify")
    assert len(calls) == 0, "run_sandboxed wurde aufgerufen, obwohl die Validierung fehlschlagen sollte"


def test_rejects_expression_with_file_io_keywords(monkeypatch):
    import src.sandbox.executor as exec_mod
    calls = []
    monkeypatch.setattr(exec_mod, "run_sandboxed", lambda *a, **kw: calls.append(1) or {"ok": True, "result": None, "error": None})

    for bad in ("openr", "load", "system", "os."):
        with pytest.raises(ValueError, match=r"(?i)invalid|disallowed|character|token"):
            evaluate(bad, "simplify")
    assert len(calls) == 0, "run_sandboxed wurde aufgerufen"


def test_unknown_operation_raises():
    with pytest.raises(ValueError, match=r"(?i)operation|simplify|differentiate|integrate|solve|limit|series|laplace"):
        evaluate("x", "delete_everything")


def test_expression_length_limit_enforced(monkeypatch):
    import src.sandbox.executor as exec_mod
    calls = []
    monkeypatch.setattr(exec_mod, "run_sandboxed", lambda *a, **kw: calls.append(1) or {"ok": True, "result": None, "error": None})

    with pytest.raises(ValueError, match=r"(?i)too long|length|500"):
        evaluate("x" * 501, "simplify")
    assert len(calls) == 0


@pytest.mark.integration
def test_runs_inside_sandbox_with_short_timeout(monkeypatch):
    import src.sandbox.executor as exec_mod
    captured = {}

    def mock_run_sandboxed(fn, args, timeout_s=5.0):
        captured["timeout"] = timeout_s
        return {"ok": True, "result": "x^2", "error": None}

    monkeypatch.setattr(exec_mod, "run_sandboxed", mock_run_sandboxed)

    evaluate("x^2", "simplify")
    assert "timeout" in captured
    assert captured["timeout"] <= 3.0, f"timeout sollte <= 3s sein, war {captured['timeout']}"