"""Sandboxed execution of SageMath code via subprocess.

This is the **single** subprocess runner for the entire service.  Both
the dispatcher (function + template operations) and any other caller go
through this module.  Resource limits (memory, CPU, processes) are set
inside the child process before any user code runs.
"""

import json
import subprocess
import sys

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
        f"resource.setrlimit(resource.RLIMIT_AS, ({_MAX_MEMORY}, {_MAX_MEMORY}))\n"
        f"resource.setrlimit(resource.RLIMIT_CPU, ({_MAX_CPU}, {_MAX_CPU}))\n"
        f"resource.setrlimit(resource.RLIMIT_NPROC, ({_MAX_PROCESSES}, {_MAX_PROCESSES}))\n"
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
    # Complex numbers → [real, imag] pair
    try:
        if isinstance(obj, complex):
            return [obj.real, obj.imag]
        # SageMath complex types (e.g. sage.rings.complex_number.ComplexNumber)
        cr = float(obj.real())
        ci = float(obj.imag())
        return [cr, ci]
    except (TypeError, AttributeError):
        pass
    try:
        return int(obj)
    except (TypeError, ValueError):
        pass
    try:
        return float(obj)
    except (TypeError, ValueError):
        pass
    return str(obj)
"""


def _run_subprocess(helper_code: str, input_data: dict | None = None,
                    timeout_s: float = 5.0) -> dict:
    """Run *helper_code* in a subprocess with resource limits and timeout.

    Returns ``{"ok": bool, "result": ..., "error": ...}``.
    """
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
        return {"ok": False, "result": None, "error": "timeout"}
    if proc.returncode != 0:
        return {
            "ok": False, "result": None,
            "error": (proc.stderr or "").strip() or f"exit code {proc.returncode}",
        }
    try:
        return json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return {
            "ok": False, "result": None,
            "error": (proc.stderr or "").strip() or "invalid output",
        }


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
        "    print(json.dumps({'ok': False, 'result': None, "
        "'error': str(_exc)}))\n"
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