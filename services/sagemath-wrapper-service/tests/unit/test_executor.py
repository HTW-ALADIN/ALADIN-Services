"""Tests for src.sandbox.executor — the single subprocess runner."""

import time

from src.sandbox.executor import run_code, run_function


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
    assert "boom" in result["error"]


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
    assert "state" in r2["error"].lower()


def test_run_code_missing_result_returns_error():
    """Code that does not set __result__ returns an error."""
    result = run_code("x = 42", timeout_s=5.0, prepend_sage_import=False)
    assert result["ok"] is False
    assert "__result__" in result["error"]