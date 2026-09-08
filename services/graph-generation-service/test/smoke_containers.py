"""Run against a started Compose deployment: python test/smoke_containers.py."""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def smoke(base: str) -> None:
    def request(path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(base + path, data=body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=40) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    if request("/readyz")[0] != 200:
        raise RuntimeError("deployment is not ready")
    dangerous: list[dict[str, Any]] = [
        {"algorithm": "classic_deterministic", "params": {"shape": "complete", "n": 10000}},
        {"algorithm": "configuration_model", "params": {"sequence": [1000000000, 1000000000]}},
        {"algorithm": "configuration_model", "backend": "graph_tool", "params": {"out": [1000000000]}},
        {
            "algorithm": "kronecker_rmat",
            "params": {"scale": 13, "edgeFactor": 1000000000, "a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25},
        },
    ]
    for payload in dangerous:
        status, result = request("/v1/graphs", payload)
        if status not in {400, 413}:
            raise RuntimeError(f"resource check failed: {status}: {result}")
    normal: list[dict[str, Any]] = [
        {"algorithm": "erdos_renyi_gnp", "backend": backend, "params": {"n": 10, "p": 0.2}}
        for backend in ("networkx", "igraph", "networkit")
    ] + [
        {"algorithm": "price_network", "params": {"n": 10, "seed": 42}},
        {"algorithm": "knn_graph", "params": {"pointGenerator": {"n": 10, "dimensions": 2, "seed": 42}, "k": 2}},
        {"algorithm": "triangulation", "params": {"points": [[0, 0], [1, 0], [0, 1], [1, 1]]}},
        {"algorithm": "configuration_model", "backend": "graph_tool", "params": {"out": [2, 2, 2, 2]}},
        {
            "algorithm": "stochastic_block_model",
            "backend": "graph_tool",
            "params": {"membership": [0, 0, 1, 1], "matrix": [[2, 0.5], [0.5, 2]]},
        },
    ]
    for payload in normal:
        status, result = request("/v1/graphs", payload)
        if status != 201:
            raise RuntimeError(f"{payload['algorithm']} failed: {status}: {result}")
        export_status, exported = request(result["_links"]["export"])
        if export_status != 200 or len(exported["edges"]) != result["metadata"]["numEdges"]:
            raise RuntimeError(f"export failed: {export_status}: {exported}")
        req = Request(base + result["_links"]["self"], method="DELETE")
        with urlopen(req, timeout=10) as response:
            if response.status != 204:
                raise RuntimeError("graph cleanup failed")
    if request("/readyz")[0] != 200:
        raise RuntimeError("deployment did not survive smoke tests")
    print("Container smoke passed: 4 hostile requests rejected; 8 generation/export paths succeeded.")


if __name__ == "__main__":
    smoke(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002")
