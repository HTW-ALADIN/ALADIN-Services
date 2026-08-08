"""Sandboxed execution of SageMath code via subprocess.

This is the **single** subprocess runner for the entire service.  Both
the dispatcher (function + template operations) and any other caller go
through this module.  Resource limits (memory, CPU, processes) are set
inside the child process before any user code runs.
"""

import json
import logging
import os
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

# Sentinel error string used when the concurrency semaphore could not be
# acquired. Callers (e.g. src.api.dynamic_routes) use this to distinguish a
# transient, retryable "server busy" condition (→ HTTP 503) from a genuine
# input/execution error (→ HTTP 400).
BUSY_ERROR = "busy"

# ── Concurrency limit ─────────────────────────────────────────────────────────
# Bounded by a semaphore so we don't overwhelm the host.  Size comes from
# env SAGE_MAX_CONCURRENCY (default 4).
_MAX_CONCURRENCY = int(os.environ.get("SAGE_MAX_CONCURRENCY", "4"))
_concurrency_sem = threading.Semaphore(_MAX_CONCURRENCY)

# ── Resource limits for the sandboxed child process ──────────────────────────
# These are set *inside* the subprocess before any user code executes.
# Values are chosen to stay well within the Docker container limit (2 GiB).

_MAX_MEMORY = 1536 * 1024 * 1024  # 1.5 GiB  (Docker limit is 2 GiB)
_MAX_CPU = 60                      # 60 seconds CPU time
_MAX_PROCESSES = 64                # prevent fork bombs


def _sandbox_preamble() -> str:
    """Python code prepended to every subprocess helper to set resource limits."""
    return (
        "import resource\n"
        # Each setrlimit is wrapped in try/except so a restrictive host
        # does not crash the child before it can report a clean error.
        # Note: RLIMIT_NPROC is per-user, not per-process, so it may fail
        # if the user already has many processes running.
        "for _rsc, _lim in [\n"
        f"    (resource.RLIMIT_AS, ({_MAX_MEMORY}, {_MAX_MEMORY})),\n"
        f"    (resource.RLIMIT_CPU, ({_MAX_CPU}, {_MAX_CPU})),\n"
        f"    (resource.RLIMIT_NPROC, ({_MAX_PROCESSES}, {_MAX_PROCESSES})),\n"
        "]:\n"
        "    try:\n"
        "        resource.setrlimit(_rsc, _lim)\n"
        "    except (ValueError, OSError):\n"
        "        pass\n"
    )


# ── Sage→JSON conversion (embedded as source in subprocess helpers) ──────────

_SAGE_TO_JSON_SOURCE = """
def _sage_to_json(obj):
    \"\"\"Recursively convert SageMath types to JSON-safe native Python types.\"\"\"
    if isinstance(obj, (bool, int, float, str, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_sage_to_json(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _sage_to_json(v) for k, v in obj.items()}
    # Complex numbers → [real, imag] pair. Sage real types (RealNumber,
    # RealDoubleElement, ...) also expose .real()/.imag(), so only take
    # this branch when the imaginary part is actually non-zero — otherwise
    # fall through to the plain float/int conversion below (using the real
    # part), so genuinely real Sage values are not corrupted into pairs.
    cr = ci = None
    try:
        if isinstance(obj, complex):
            cr, ci = obj.real, obj.imag
        else:
            # SageMath complex types (e.g. sage.rings.complex_number.ComplexNumber)
            cr, ci = float(obj.real()), float(obj.imag())
    except (TypeError, AttributeError):
        pass
    if ci is not None and ci != 0:
        return [cr, ci]
    if cr is not None:
        obj = cr
    # Try float() before int() so rationals like 1/2 don't truncate to 0.
    # Keep exact ints as ints — if the float value is integral and the
    # original object is not a Rational/Fraction, return int.
    try:
        obj_is_rational = any(
            type(obj).__name__ == t
            for t in ("Rational", "Fraction")
        )
        val = float(obj)
        if not obj_is_rational and val == int(val) and not isinstance(val, bool):
            return int(val)
        return val
    except (TypeError, ValueError):
        pass
    try:
        return int(obj)
    except (TypeError, ValueError):
        pass
    return str(obj)
"""


def _run_subprocess(helper_code: str, input_data: dict | None = None,
                    timeout_s: float = 5.0) -> dict:
    """Run *helper_code* in a subprocess with resource limits and timeout.

    Concurrency is bounded by ``_concurrency_sem``.  If the semaphore cannot
    be acquired within a short timeout, returns ``{"ok": False, ..., "error": "busy"}``.

    Returns ``{"ok": bool, "result": ..., "error": ...}``.
    """
    # Try to acquire the concurrency slot
    if not _concurrency_sem.acquire(blocking=True, timeout=2.0):
        return {"ok": False, "result": None, "error": BUSY_ERROR}
    try:
        full_code = _sandbox_preamble() + _SAGE_TO_JSON_SOURCE + helper_code
        try:
            proc = subprocess.run(
                [sys.executable, "-c", full_code],
                input=json.dumps(input_data) if input_data is not None else None,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning("subprocess timed out after %.1fs", timeout_s)
            return {"ok": False, "result": None, "error": "timeout"}
        if proc.returncode != 0:
            _stderr = (proc.stderr or "").strip()
            if _stderr:
                logger.warning("subprocess stderr (rc=%d): %s", proc.returncode, _stderr)
            return {
                "ok": False, "result": None,
                "error": "execution failed",
            }
        try:
            return json.loads(proc.stdout)
        except Exception:  # noqa: BLE001
            _stderr = (proc.stderr or "").strip()
            if _stderr:
                logger.warning("subprocess parse error, stderr: %s", _stderr)
            return {
                "ok": False, "result": None,
                "error": "invalid output",
            }
    finally:
        _concurrency_sem.release()


def run_function(fn_ref: str, args: dict, timeout_s: float = 5.0) -> dict:
    """Execute ``fn_ref(**args)`` in a sandboxed subprocess.

    *fn_ref* is a ``"module:function"`` string (e.g. ``"src.core.linalg:determinant"``).
    The result is converted to JSON-safe native types via ``_sage_to_json``.
    """
    module_path, func_name = fn_ref.split(":", 1)
    helper = (
        "import json, sys\n"
        f"from {module_path} import {func_name} as _fn\n"
        "try:\n"
        "    _result = _fn(**json.loads(sys.stdin.read()))\n"
        "    print(json.dumps({'ok': True, 'result': _sage_to_json(_result), "
        "'error': None}))\n"
        "except BaseException as _exc:\n"
        "    _tname = type(_exc).__name__\n"
        "    print(json.dumps({'ok': False, 'result': None, "
        "'error': _tname}))\n"
    )
    return _run_subprocess(helper, input_data=args, timeout_s=timeout_s)


def run_code(code: str, timeout_s: float = 5.0,
             prepend_sage_import: bool = True) -> dict:
    """Execute *code* in a sandboxed subprocess and extract ``__result__``.

    When *prepend_sage_import* is ``True`` (default), prepends
    ``from sage.all import *`` so template code can use ``Matrix``,
    ``vector``, etc. directly.  The code must set ``__result__``.
    The result is converted to JSON-safe native types via ``_sage_to_json``.
    """
    if prepend_sage_import:
        code = "from sage.all import *\n" + code
    helper = (
        "import json, sys\n"
        "ns = {}\n"
        f"exec({code!r}, ns)\n"
        "if '__result__' not in ns:\n"
        "    print(json.dumps({'ok': False, 'result': None, "
        "'error': '__result__ not set by template'}))\n"
        "else:\n"
        "    print(json.dumps({'ok': True, 'result': "
        "_sage_to_json(ns['__result__']), 'error': None}))\n"
    )
    return _run_subprocess(helper, timeout_s=timeout_s)