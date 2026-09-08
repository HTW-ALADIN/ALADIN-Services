from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from graph_tool_sidecar.generation import generate
from graph_tool_sidecar.main import app as sidecar_app
from graph_tool_sidecar.models import SidecarRequest

sidecar_client = TestClient(sidecar_app)


class FakeVertex:
    def __init__(self, index: int) -> None:
        self.index = index

    def __int__(self) -> int:
        return self.index


class FakeEdge:
    def __init__(self, source: int, target: int) -> None:
        self._source = FakeVertex(source)
        self._target = FakeVertex(target)

    def source(self) -> FakeVertex:
        return self._source

    def target(self) -> FakeVertex:
        return self._target


class FakeGraph:
    def __init__(self, *, directed: bool = False) -> None:
        self.directed = directed

    def num_vertices(self) -> int:
        return 3

    def edges(self) -> list[FakeEdge]:
        return [FakeEdge(0, 1), FakeEdge(1, 2)]

    def is_directed(self) -> bool:
        return self.directed


@pytest.mark.parametrize(
    ("sidecar_request", "method_name", "returns_tuple"),
    [
        (
            SidecarRequest(
                algorithm="configuration_model",
                params={"out": [2, 2, 2], "seed": 1},
            ),
            "random_graph",
            False,
        ),
        (
            SidecarRequest(
                algorithm="stochastic_block_model",
                params={"membership": [0, 0, 1], "matrix": [[2.0, 0.5], [0.5, 1.0]]},
            ),
            "generate_sbm",
            False,
        ),
        (
            SidecarRequest(
                algorithm="knn_graph",
                params={"pointGenerator": {"n": 3, "dimensions": 2, "seed": 1}, "k": 1},
                directed=True,
            ),
            "generate_knn",
            True,
        ),
        (
            SidecarRequest(
                algorithm="triangulation",
                params={"points": [[0, 0], [1, 0], [0, 1]], "type": "delaunay"},
            ),
            "triangulation",
            True,
        ),
        (
            SidecarRequest(
                algorithm="price_network",
                params={"n": 3, "m": 1, "seed": 1},
                directed=True,
            ),
            "price_network",
            False,
        ),
    ],
)
def test_routes_all_graph_tool_operations(
    sidecar_request: SidecarRequest,
    method_name: str,
    returns_tuple: bool,
) -> None:
    graph_tool = MagicMock()
    generation = MagicMock()
    graph = FakeGraph(directed=sidecar_request.directed)
    setattr(generation, method_name, MagicMock(return_value=(graph, object()) if returns_tuple else graph))

    with patch(
        "graph_tool_sidecar.generation.import_module",
        side_effect=[graph_tool, generation],
    ):
        result = generate(sidecar_request)

    getattr(generation, method_name).assert_called_once()
    assert result.nodes == [0, 1, 2]
    assert result.edges == [(0, 1), (1, 2)]
    assert result.directed is sidecar_request.directed
    if sidecar_request.params.get("seed") is not None:
        graph_tool.seed_rng.assert_called_once_with(sidecar_request.params["seed"])


def test_point_generator_is_reproducible() -> None:
    generation = MagicMock()
    generation.generate_knn.return_value = (FakeGraph(), object())
    request = SidecarRequest(
        algorithm="knn_graph",
        params={"pointGenerator": {"n": 3, "dimensions": 2, "seed": 7}, "k": 1},
    )

    with patch("graph_tool_sidecar.generation.import_module", side_effect=[MagicMock(), generation]):
        generate(request)
        first_points = generation.generate_knn.call_args.args[0]
    generation.reset_mock()
    with patch("graph_tool_sidecar.generation.import_module", side_effect=[MagicMock(), generation]):
        generate(request)
        second_points = generation.generate_knn.call_args.args[0]

    np.testing.assert_array_equal(first_points, second_points)


@patch("graph_tool_sidecar.main.generate")
def test_sidecar_http_endpoint_returns_normalized_graph(mock_generate: MagicMock) -> None:
    mock_generate.return_value = {"nodes": [0, 1], "edges": [[0, 1]], "directed": False}

    response = sidecar_client.post(
        "/v1/generate",
        json={"algorithm": "price_network", "params": {"n": 2}, "directed": False},
    )

    assert response.status_code == 200
    assert response.json() == {"nodes": [0, 1], "edges": [[0, 1]], "directed": False}


@patch("graph_tool_sidecar.main.generate", side_effect=ValueError("invalid graph parameters"))
def test_sidecar_http_endpoint_translates_generation_errors(_mock_generate: MagicMock) -> None:
    response = sidecar_client.post(
        "/v1/generate",
        json={"algorithm": "price_network", "params": {"n": 2}, "directed": False},
    )

    assert response.status_code == 422
    assert "invalid graph parameters" in response.json()["detail"]


@patch("graph_tool_sidecar.main.import_module")
def test_sidecar_health_checks_graph_tool_import(mock_import: MagicMock) -> None:
    mock_import.return_value = MagicMock()

    response = sidecar_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "payload",
    [
        {"algorithm": "price_network", "params": {"n": 1_000_000, "m": 1}, "directed": True},
        {
            "algorithm": "stochastic_block_model",
            "params": {"membership": [0] * 10_000, "matrix": [[1.0]]},
            "directed": True,
        },
        {"algorithm": "configuration_model", "params": {"out": [5_000_000]}, "directed": False},
        {
            "algorithm": "knn_graph",
            "params": {"points": [[0.0, 0.0]] * 10_000, "k": 1_000},
            "directed": False,
        },
    ],
)
def test_sidecar_rejects_oversized_requests(payload: dict[str, object]) -> None:
    response = sidecar_client.post("/v1/generate", json=payload)

    assert response.status_code == 422
