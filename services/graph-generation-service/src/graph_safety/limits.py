from __future__ import annotations

import os
from dataclasses import dataclass


class ResourceLimitError(ValueError):
    def __init__(self, detail: str, status: int = 413) -> None:
        self.status = status
        super().__init__(detail)


def setting(name: str, default: int) -> int:
    value = int(os.environ.get(f"GRAPH_{name}", str(default)))
    if value <= 0:
        raise ValueError(f"GRAPH_{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Limits:
    nodes: int = 10_000
    edges: int = 100_000
    work: int = 2_000_000
    request_bytes: int = 1_048_576
    result_bytes: int = 16_777_216
    export_bytes: int = 8_388_608
    stored_bytes: int = 134_217_728
    stored_graphs: int = 100
    seconds: int = 20
    memory_bytes: int = 2_147_483_648
    concurrency: int = 2

    @classmethod
    def from_env(cls) -> Limits:
        defaults = cls()
        return cls(**{name: setting(name.upper(), getattr(defaults, name)) for name in cls.__dataclass_fields__})


LIMITS = Limits.from_env()


def check_result(nodes: int, edges: int) -> None:
    if nodes > LIMITS.nodes or edges > LIMITS.edges:
        raise ResourceLimitError("generated graph exceeds the node or edge limit")
