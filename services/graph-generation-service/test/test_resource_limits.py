from __future__ import annotations

import asyncio
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from starlette.types import Message

from app.cli import _read_request, run
from app.domain import GeneratedGraph
from app.exporters import BoundedWriter, export_isolated
from app.main import GRAPH_STORE, _graph_resource, app
from app.routing import execute_isolated
from app.schemas import GraphGenerationRequest, RequestParameterError, validate_graph_size
from app.storage import GraphStore, StoredGraph
from graph_safety.http import BodyLimitMiddleware
from graph_safety.limits import LIMITS, ResourceLimitError
from graph_safety.process import run_worker

ADAPTER: TypeAdapter[GraphGenerationRequest] = TypeAdapter(GraphGenerationRequest)
SMALL = {"algorithm": "classic_deterministic", "backend": "networkx", "params": {"shape": "path", "n": 5}}


@pytest.mark.parametrize(
    "payload",
    [
        {"algorithm": "classic_deterministic", "params": {"shape": "complete", "n": 10_000}},
        {"algorithm": "configuration_model", "params": {"sequence": [1_000_000_000, 1_000_000_000]}},
        {
            "algorithm": "kronecker_rmat",
            "params": {"scale": 13, "edgeFactor": 1_000_000_000, "a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25},
        },
        {"algorithm": "random_geometric", "params": {"n": 2, "radius": 0.5, "dim": 1_000_000_000}},
        {"algorithm": "knn_graph", "params": {"pointGenerator": {"n": 10_000}, "k": 9999}},
        {
            "algorithm": "stochastic_block_model",
            "backend": "graph_tool",
            "params": {"membership": [0, 0], "matrix": [[1e12]]},
        },
        {"algorithm": "random_tree", "params": {"n": 1000, "variant": "random_powerlaw", "tries": 10_000}},
    ],
)
def test_dangerous_requests_rejected_before_execution(payload: dict[str, Any]) -> None:
    with patch("app.main.execute_request") as execute:
        response = TestClient(app).post("/v1/graphs", json=payload)
    assert response.status_code in {400, 413}
    assert response.headers["content-type"] == "application/problem+json"
    execute.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "algorithm": "community_clustered",
            "params": {"variant": "relaxed_caveman", "n": 1, "l": 101, "k": 100, "p": 0},
        },
        {"algorithm": "static_fitness", "params": {"n": 1, "m": 1, "fitness_out": [1] * 10_001}},
    ],
)
def test_unused_n_cannot_hide_actual_node_count(payload: dict[str, Any]) -> None:
    with pytest.raises(RequestParameterError, match="10000"):
        validate_graph_size(ADAPTER.validate_python(payload))


def test_body_limit_before_json_decode_on_both_services() -> None:
    from graph_tool_sidecar.main import app as sidecar

    with patch("graph_safety.http.LIMITS", replace(LIMITS, request_bytes=8)):
        for service, path in [(app, "/v1/graphs"), (sidecar, "/v1/generate")]:
            response = TestClient(service).post(path, content=b"x" * 9)
            assert response.status_code == 413


def test_chunked_body_limit_without_content_length() -> None:
    sent: list[Message] = []
    chunks = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )

    async def receive() -> Message:
        return next(chunks)

    async def send(message: Message) -> None:
        sent.append(message)

    async def never_called(*args: Any) -> None:
        pytest.fail("oversized body reached the application")

    with patch("graph_safety.http.LIMITS", replace(LIMITS, request_bytes=8)):
        asyncio.run(BodyLimitMiddleware(never_called)({"type": "http", "method": "POST"}, receive, send))
    assert sent[0]["status"] == 413


def test_cli_file_and_http_share_byte_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file = tmp_path / "large.json"
    file.write_bytes(b"x" * 9)
    with patch("app.cli.LIMITS", replace(LIMITS, request_bytes=8)):
        with pytest.raises(ResourceLimitError):
            _read_request(str(file))
        assert run(["generate", "{123456789}"]) == 2
    assert "byte limit" in capsys.readouterr().err


def test_real_worker_generation_export_and_lifecycle() -> None:
    GRAPH_STORE.clear()
    client = TestClient(app)
    response = client.post("/v1/graphs", json=SMALL)
    assert response.status_code == 201, response.text
    graph = response.json()
    exported = client.get(graph["_links"]["export"])
    assert exported.status_code == 200
    assert len(exported.json()["nodes"]) == 5
    assert len(exported.json()["edges"]) == 4
    assert client.delete(graph["_links"]["self"]).status_code == 204


def test_deadline_kills_child_and_releases_slot() -> None:
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def slow_worker(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(process)
        return process

    with (
        patch("graph_safety.process.LIMITS", replace(LIMITS, seconds=1)),
        patch("graph_safety.process.subprocess.Popen", side_effect=slow_worker),
    ):
        with pytest.raises(ResourceLimitError) as error:
            run_worker("primary", SMALL)
    assert error.value.status == 504
    assert children[0].poll() is not None
    assert run_worker("primary", SMALL)["nodes"] == list(range(5))


def test_worker_crash_is_contained() -> None:
    real_popen = subprocess.Popen

    def crash_worker(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-c", "import os; os._exit(134)"], **kwargs)

    with patch("graph_safety.process.subprocess.Popen", side_effect=crash_worker):
        with pytest.raises(ResourceLimitError) as error:
            run_worker("primary", SMALL)
    assert error.value.status == 503
    assert execute_isolated(ADAPTER.validate_python(SMALL)).num_nodes == 5


def test_worker_capacity_rejects_without_queueing() -> None:
    from threading import BoundedSemaphore

    slots = BoundedSemaphore(1)
    slots.acquire()
    with patch("graph_safety.process.SLOTS", slots), patch("graph_safety.process.subprocess.Popen") as spawn:
        with pytest.raises(ResourceLimitError) as error:
            run_worker("primary", SMALL)
    assert error.value.status == 503
    spawn.assert_not_called()


def test_sidecar_independently_rejects_dangerous_input() -> None:
    with pytest.raises(ResourceLimitError) as error:
        run_worker("sidecar", {"algorithm": "configuration_model", "params": {"out": [1_000_000_000]}})
    assert error.value.status == 400


def test_graph_tool_sbm_budget_is_not_skipped() -> None:
    request = ADAPTER.validate_python(
        {
            "algorithm": "stochastic_block_model",
            "backend": "graph_tool",
            "params": {"membership": [0, 0], "matrix": [[200_000]]},
        }
    )
    with pytest.raises(ResourceLimitError, match="edge budget"):
        validate_graph_size(request)


def test_lattice_dimensions_rejected_before_combinatorial_estimation() -> None:
    payload = {
        "algorithm": "watts_strogatz",
        "backend": "igraph",
        "params": {"dim": 1_000_000, "size": 1, "nei": 1_000_000, "p": 0.1},
    }
    with patch("app.schemas._estimate_expected_edges") as estimate:
        response = TestClient(app).post("/v1/graphs", json=payload)
    assert response.status_code == 400
    estimate.assert_not_called()


def stored_graph(n: int = 5) -> StoredGraph:
    request = ADAPTER.validate_python(SMALL)
    graph = nx.path_graph(n)
    generated = GeneratedGraph(graph, n, n - 1, False)
    return StoredGraph(_graph_resource(request, generated, 0), generated, "index")


def test_store_rejects_oversized_entry_without_flushing() -> None:
    store = GraphStore()
    with patch("app.storage.LIMITS", replace(LIMITS, stored_bytes=30_000)):
        store.put("old", stored_graph(), capacity=100)
        with pytest.raises(ResourceLimitError):
            store.put("oversized", stored_graph(100), capacity=100)
    assert store.get("old") is not None
    assert len(store) == 1


def test_store_evicts_by_bytes_below_count_limit() -> None:
    store = GraphStore()
    with patch("app.storage.LIMITS", replace(LIMITS, stored_bytes=30_000)):
        store.put("first", stored_graph(), capacity=100)
        store.put("second", stored_graph(), capacity=100)
    assert store.get("first") is None
    assert store.get("second") is not None
    assert len(store) == 1


@pytest.mark.parametrize("preexisting", [False, True])
def test_store_rejects_entry_larger_than_edge_budget(preexisting: bool) -> None:
    store = GraphStore()
    if preexisting:
        store.put("old", stored_graph(2), capacity=100, edge_capacity=3)
    with pytest.raises(ResourceLimitError, match="storage capacity"):
        store.put("oversized", stored_graph(5), capacity=100, edge_capacity=3)
    assert store.get("oversized") is None
    assert len(store) == int(preexisting)
    if preexisting:
        assert store.get("old") is not None


def test_request_capacity_rejects_before_reading_and_keeps_health_available() -> None:
    from threading import BoundedSemaphore

    sent: list[Message] = []
    calls: list[str] = []

    async def receive() -> Message:
        pytest.fail("saturated request body should not be read")

    async def send(message: Message) -> None:
        sent.append(message)

    async def endpoint(scope: Any, *args: Any) -> None:
        calls.append(scope["path"])

    middleware = BodyLimitMiddleware(endpoint)
    middleware.slots = BoundedSemaphore(1)
    middleware.slots.acquire()
    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/v1/graphs"}, receive, send))
    assert sent[0]["status"] == 503
    asyncio.run(middleware({"type": "http", "path": "/healthz"}, receive, send))
    assert calls == ["/healthz"]


def test_export_worker_rejects_json_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_EXPORT_BYTES", "8")
    with pytest.raises(ResourceLimitError) as error:
        run_worker(
            "export",
            {
                "nodes": [0, 1],
                "edges": [[0, 1]],
                "directed": False,
                "format": "edge_list",
                "labels": "index",
                "id": "test",
            },
        )
    assert error.value.status == 413


def test_store_concurrent_admission_stays_within_capacity() -> None:
    store = GraphStore()
    value = stored_graph()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: store.put(str(i), value, capacity=3), range(50)))
    assert len(store) == 3
    assert store.delete("absent") is False


def test_export_budget_is_enforced_before_writing_excess() -> None:
    with patch("app.exporters.LIMITS", replace(LIMITS, export_bytes=8)):
        output = BoundedWriter()
        output.write(b"12345678")
        with pytest.raises(ResourceLimitError):
            output.write(b"9")
        assert output.getvalue() == b"12345678"


def test_multigraph_graphml_preserves_parallel_edges() -> None:
    graph: nx.MultiGraph[int] = nx.MultiGraph()
    graph.add_edges_from([(0, 1), (0, 1)])
    result = export_isolated(
        GeneratedGraph(graph, 2, 2, False), output_format="graphml", labels="index", resource_id="test"
    )
    assert isinstance(result.content, bytes)
    decoded = nx.parse_graphml(result.content.decode())
    assert decoded.number_of_edges() == 2
    with pytest.raises(ValueError):
        run_worker(
            "export",
            {
                "nodes": [0, 1],
                "edges": [[0, 1], [0, 1]],
                "directed": False,
                "format": "graph6",
                "labels": "index",
                "id": "test",
            },
        )


def test_bounded_sidecar_response_read() -> None:
    from app.adapters.graph_tool_adapter import generate_price_network

    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b"x" * 9
    with (
        patch("app.adapters.graph_tool_adapter.LIMITS", replace(LIMITS, result_bytes=8)),
        patch("app.adapters.graph_tool_adapter.urlopen", return_value=response),
    ):
        with pytest.raises(ResourceLimitError):
            generate_price_network(n=5)
    response.read.assert_called_once_with(9)


def test_invalid_parameters_return_structured_error_from_worker() -> None:
    response = TestClient(app).post("/v1/graphs", json={"algorithm": "barabasi_albert", "params": {"n": 2, "m": 3}})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_openapi_documents_resource_errors() -> None:
    responses = app.openapi()["paths"]["/v1/graphs"]["post"]["responses"]
    assert {"413", "503", "504"} <= responses.keys()


def test_runtime_guards_remain_active_under_python_optimization() -> None:
    code = """
from app.adapters import networkx_adapter as nx, igraph_adapter as ig, networkit_adapter as nk
cases = [
    (nx.generate_classic_deterministic, {'shape': 'grid'}),
    (nx.generate_classic_deterministic, {'shape': 'complete'}),
    (nx.generate_random_bipartite, {'n1': 2, 'n2': 2}),
    (ig.generate_classic_deterministic, {'shape': 'grid'}),
    (ig.generate_classic_deterministic, {'shape': 'complete'}),
    (ig.generate_static_fitness, {'variant': 'static_fitness', 'm': 2}),
    (ig.generate_static_fitness, {'variant': 'static_power_law', 'm': 2}),
    (nk.generate_community_clustered, {'variant': 'clustered_random', 'n': 10}),
    (nk.generate_community_clustered, {'variant': 'lfr', 'n': 10}),
]
for variant in ('planted_partition', 'gaussian_random_partition', 'relaxed_caveman', 'lfr'):
    cases.append((nx.generate_community_clustered, {'variant': variant}))
for variant in ('waxman', 'geographical_threshold'):
    cases.append((nx.generate_geometric_threshold, {'variant': variant, 'n': 10}))
for variant in ('growing_random', 'establishment', 'preference', 'asymmetric_preference', 'recent_degree'):
    cases.append((ig.generate_growing_attachment, {'variant': variant, 'n': 10, 'directed': False}))
for function, arguments in cases:
    try:
        function(**arguments)
    except ValueError:
        continue
    raise RuntimeError('runtime precondition was not enforced')
print(len(cases))
"""
    result = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "20"
