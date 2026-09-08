from __future__ import annotations

import json
import os
import resource
import sys
from importlib import import_module
from typing import Any

from graph_safety.limits import LIMITS, ResourceLimitError


def main() -> None:
    # Native libraries can print to fd 1; keep their output out of the result protocol.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    # Apply limits before importing any native graph library. AS is reliable on Linux.
    resource.setrlimit(resource.RLIMIT_CPU, (LIMITS.seconds, LIMITS.seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS.result_bytes, LIMITS.result_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS.memory_bytes, LIMITS.memory_bytes))
    targets = {
        "primary": ("app.routing", "worker_generate"),
        "sidecar": ("graph_tool_sidecar.generation", "worker_generate"),
        "export": ("app.exporters", "worker_export"),
    }
    message: dict[str, Any]
    try:
        module, name = targets[sys.argv[1]]
        raw = sys.stdin.buffer.read(LIMITS.result_bytes + 1)
        if len(raw) > LIMITS.result_bytes:
            raise ResourceLimitError("worker input exceeds the byte limit")
        result = getattr(import_module(module), name)(json.loads(raw))
        message = {"result": result}
    except ResourceLimitError as exc:
        message = {"error": str(exc), "status": exc.status}
    except MemoryError:
        message = {"error": "graph worker exceeded memory limit", "status": 413}
    except Exception:
        message = {"error": "graph backend rejected the parameters or failed", "status": 400}
    size = 0
    for chunk in json.JSONEncoder(allow_nan=False).iterencode(message):
        data = chunk.encode()
        size += len(data)
        if size > LIMITS.result_bytes:
            raise ResourceLimitError("worker response exceeds the byte limit")
        output.write(data)
    output.close()


if __name__ == "__main__":
    main()
