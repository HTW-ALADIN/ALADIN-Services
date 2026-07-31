"""Sandboxed execution of user-supplied SageMath code."""

import os
import resource
import signal
from multiprocessing import Pipe


def run_sandboxed(fn, args, timeout_s=5.0):
    """Execute fn(**args) in a subprocess with timeout and resource limits."""
    parent_conn, child_conn = Pipe(duplex=False)
    pid = os.fork()

    if pid == 0:
        parent_conn.close()
        try:
            resource.setrlimit(resource.RLIMIT_AS, (104857600, 104857600))
        except (OSError, ValueError):
            pass
        try:
            child_conn.send({"ok": True, "result": fn(**args), "error": None})
        except MemoryError:
            child_conn.send({"ok": False, "result": None, "error": "memory limit exceeded"})
        except BaseException as exc:  # noqa: BLE001
            try:
                child_conn.send({"ok": False, "result": None, "error": str(exc)})
            except BaseException:  # noqa: BLE001,S110
                pass
        os._exit(0)

    # ── parent process ──
    child_conn.close()
    if parent_conn.poll(timeout_s):
        try:
            result = parent_conn.recv()
        except (EOFError, OSError):
            result = {"ok": False, "result": None, "error": "child crashed"}
        parent_conn.close()
        os.waitpid(pid, 0)
        return result

    # Timeout — kill the child
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    parent_conn.close()
    return {"ok": False, "result": None, "error": "timeout"}


def run_sandboxed_code(code: str, timeout_s: float = 5.0) -> dict:
    """Execute *code* in a sandboxed subprocess and extract ``__result__``.

    The code must set a variable ``__result__`` with the return value.
    Raises ``ValueError`` if ``__result__`` is not set.
    """
    def _run():
        ns: dict = {}
        exec(code, ns)  # noqa: S102
        if "__result__" not in ns:
            raise ValueError("__result__ not set by template")
        return ns["__result__"]

    return run_sandboxed(_run, {}, timeout_s=timeout_s)