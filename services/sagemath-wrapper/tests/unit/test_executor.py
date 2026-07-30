import time

import pytest

from src.sandbox.executor import run_sandboxed


def test_returns_ok_true_for_successful_function():
    result = run_sandboxed(lambda a, b: a + b, {"a": 2, "b": 3})
    assert result == {"ok": True, "result": 5, "error": None}


def test_timeout_returns_ok_false():
    t0 = time.monotonic()
    result = run_sandboxed(lambda: time.sleep(10), {}, timeout_s=0.5)
    elapsed = time.monotonic() - t0

    assert result["ok"] is False
    assert "timeout" in result["error"].lower()
    assert elapsed < 2.0, f"test took {elapsed:.2f}s, expected < 2s"


def test_exception_fn_is_captured_not_raised():
    def _raise():
        raise ValueError("bad input")

    result = run_sandboxed(_raise, {})
    assert result["ok"] is False
    assert "bad input" in result["error"]


@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="memory limit test only supported on Linux",
)
def test_memory_limit_enforced():
    def _alloc():
        arr = bytearray(300 * 1024 * 1024)  # ~300 MB
        return len(arr)

    result = run_sandboxed(_alloc, {}, timeout_s=10.0)
    assert result["ok"] is False
    assert any(kw in result["error"].lower() for kw in ("memory", "limit"))


def test_no_shared_state_between_calls():
    """Zwei Aufrufe teilen keinen globalen Zustand (Prozessisolation)."""

    code = """
data = {}
def mutate(k, v):
    import json
    data[k] = v
    return json.dumps(data)
"""
    # Modul mit exec bauen, damit wir einen echten fn mit global state haben
    ns = {}
    exec(code, ns)  # noqa: S102 — intentional, creates fn with module-level state
    fn = ns["mutate"]

    r1 = run_sandboxed(fn, {"k": "a", "v": 1})
    assert r1["ok"] is True

    # Zweiter Aufruf – das data-Dict des ersten muss weg sein
    r2 = run_sandboxed(fn, {"k": "b", "v": 2})
    assert r2["ok"] is True
    assert r2["result"] == '{"b": 2}', (
        f"erwartet isoliertes Dict, bekam {r2['result']}"
    )