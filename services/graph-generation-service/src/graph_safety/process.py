from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore
from typing import Any

from graph_safety.limits import LIMITS, ResourceLimitError

SLOTS = BoundedSemaphore(LIMITS.concurrency)


def run_worker(target: str, payload: dict[str, Any]) -> Any:
    """One disposable interpreter per job; no native work survives its deadline."""
    data = json.dumps(payload, allow_nan=False).encode()
    if len(data) > LIMITS.result_bytes:
        raise ResourceLimitError("worker input exceeds the byte limit")
    if not SLOTS.acquire(blocking=False):
        raise ResourceLimitError("generation workers are busy; retry later", 503)
    try:
        with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output:
            source.write(data)
            source.seek(0)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
            env["PYTHONPATH"] = os.pathsep.join(sys.path)
            with subprocess.Popen(
                [sys.executable, "-m", "graph_safety.worker", target],
                stdin=source,
                stdout=output,
                stderr=subprocess.DEVNULL,
                env=env,
            ) as process:
                try:
                    process.wait(timeout=LIMITS.seconds)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    process.wait()
                    raise ResourceLimitError("graph execution exceeded its deadline", 504) from exc
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
                if process.returncode != 0:
                    raise ResourceLimitError("graph worker exceeded resources or terminated unexpectedly", 503)
            output.seek(0)
            raw = output.read(LIMITS.result_bytes + 1)
            if len(raw) > LIMITS.result_bytes:
                raise ResourceLimitError("worker response exceeds the byte limit")
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise ResourceLimitError("graph worker returned an invalid response", 502) from exc
            if "error" in message:
                raise ResourceLimitError(message["error"], message["status"])
            return message["result"]
    finally:
        SLOTS.release()
