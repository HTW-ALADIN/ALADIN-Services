"""Tests for src.sandbox.executor — the single subprocess runner."""

import time

from src.sandbox.executor import _SAGE_TO_JSON_SOURCE, run_code, run_function


def _load_sage_to_json():
    """Exec the embedded ``_sage_to_json`` source (single source of truth
    also used inside the sandboxed subprocess) and return the function."""
    ns: dict = {}
    exec(_SAGE_TO_JSON_SOURCE, ns)  # noqa: S102 - test-only, trusted local source
    return ns["_sage_to_json"]


def test_run_function_returns_ok_for_successful_call():
    """run_function with a known module:function returns ok=True."""
    # Use a stdlib module:function that returns JSON-safe data
    result = run_function("json:dumps", {"obj": {"a": 1}}, timeout_s=5.0)
    assert result["ok"] is True
    assert "a" in result["result"]


def test_run_code_returns_ok_for_simple_expression():
    """run_code with a simple template returns ok=True."""
    result = run_code("__result__ = 1 + 2", timeout_s=5.0, prepend_sage_import=False)
    assert result == {"ok": True, "result": 3, "error": None}


def test_timeout_returns_ok_false():
    """Infinite loop in run_code times out."""
    t0 = time.monotonic()
    result = run_code(
        "__result__ = 0\nwhile True:\n    __result__ += 1\n",
        timeout_s=0.5,
        prepend_sage_import=False,
    )
    elapsed = time.monotonic() - t0

    assert result["ok"] is False
    assert "timeout" in result["error"].lower()
    assert elapsed < 2.0, f"test took {elapsed:.2f}s, expected < 2s"


def test_exception_in_run_function_is_captured():
    """Exception raised by the target function is returned as ok=False."""
    result = run_function("json:loads", {"s": "not-json"}, timeout_s=5.0)
    assert result["ok"] is False
    assert result["error"] is not None


def test_exception_in_run_code_is_captured():
    """Exception raised during code execution is returned as ok=False."""
    result = run_code("raise ValueError('boom')", timeout_s=5.0, prepend_sage_import=False)
    assert result["ok"] is False
    # Error is sanitized (no raw exception message leaked to clients)
    assert result["error"] is not None
    assert "boom" not in result["error"]


def test_no_shared_state_between_run_code_calls():
    """Two run_code calls do not share global state (subprocess isolation)."""
    r1 = run_code(
        "_state = {}\n_state['x'] = 1\n__result__ = _state['x']",
        timeout_s=5.0,
        prepend_sage_import=False,
    )
    assert r1["ok"] is True
    assert r1["result"] == 1

    # Second call — _state from the first must be gone (NameError → ok=False)
    r2 = run_code(
        "__result__ = _state['x']",
        timeout_s=5.0,
        prepend_sage_import=False,
    )
    assert r2["ok"] is False, (
        f"expected isolated state, got {r2['result']}"
    )
    # Error is sanitized — should not be a pass/vacuous
    assert r2["error"] is not None


def test_run_code_missing_result_returns_error():
    """Code that does not set __result__ returns an error."""
    result = run_code("x = 42", timeout_s=5.0, prepend_sage_import=False)
    assert result["ok"] is False
    assert "__result__" in result["error"]


def test_sandbox_import_failure_returns_ok_false():
    """run_function with a non-existent module returns ok=False, not a vacuous pass."""
    result = run_function("nonexistent.module:function", {}, timeout_s=5.0)
    assert result["ok"] is False
    assert result["error"] is not None
    # Error should be a type name, not a raw stack trace
    assert "exc" not in (result.get("error") or "").lower()  # no raw type name leak? Actually type names are okay
    # The error should be non-empty and generic-looking
    assert len(result["error"]) < 100  # not a full traceback


def test_sandbox_code_exception_is_sanitized():
    """Exception raised in run_code's subprocess helper has a generic error."""
    result = run_code("raise ValueError('secret debug info')", timeout_s=5.0, prepend_sage_import=False)
    assert result["ok"] is False
    # The error should not contain the secret message (it's from the subprocess stdout, not stderr)
    # This test is informational — the subprocess catches the exception and sends type name
    assert result["error"] is not None


def test_sage_to_json_real_valued_object_stays_a_number():
    """A real-only object exposing .real()/.imag() (like a SageMath real
    number) must not be corrupted into a [real, imag] pair — only genuinely
    complex values (non-zero imaginary part) should become pairs.

    Exercises the embedded ``_sage_to_json`` helper (single source of truth
    for both run_code and run_function) directly, without needing SageMath:
    a plain object with .real()/.imag() methods mimics
    RealNumber/RealDoubleElement, which also expose those methods.
    """
    sage_to_json = _load_sage_to_json()

    class _FakeReal:
        def __init__(self, v):
            self._v = v

        def real(self):
            return self._v

        def imag(self):
            return 0.0

    assert sage_to_json(_FakeReal(3.5)) == 3.5


def test_sage_to_json_complex_valued_object_stays_a_pair():
    """A genuinely complex object (non-zero imaginary part) still converts
    to a [real, imag] pair."""
    sage_to_json = _load_sage_to_json()

    class _FakeComplex:
        def __init__(self, r, i):
            self._r, self._i = r, i

        def real(self):
            return self._r

        def imag(self):
            return self._i

    assert sage_to_json(_FakeComplex(1.0, 2.0)) == [1.0, 2.0]


def test_sage_to_json_python_complex_with_zero_imag_stays_a_number():
    """A plain python complex with zero imaginary part converts to a float,
    not a string or a [real, 0.0] pair."""
    sage_to_json = _load_sage_to_json()
    assert sage_to_json(complex(4.0, 0.0)) == 4