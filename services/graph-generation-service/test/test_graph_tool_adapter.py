import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import networkx
import pytest

from app.adapters import graph_tool_adapter
from app.exceptions import GraphBackendError
from app.exporters import export_graph


def _response(body: object, *, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = json.dumps(body).encode()
    response.__enter__.return_value = response
    return response


@patch("app.adapters.graph_tool_adapter.urlopen")
def test_price_network_calls_sidecar_and_normalizes_graph(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _response({"nodes": [0, 1, 2], "edges": [[0, 1], [2, 1]], "directed": True})

    generated = graph_tool_adapter.generate_price_network(n=3, m=1, seed=42, directed=True)

    assert isinstance(generated.graph, networkx.MultiDiGraph)
    assert generated.num_nodes == 3
    assert generated.num_edges == 2
    assert generated.directed is True
    exported = export_graph(generated, output_format="edge_list", labels="index", resource_id="test")
    assert exported.content == {
        "format": "edge_list",
        "directed": True,
        "nodes": [0, 1, 2],
        "edges": [[0, 1], [2, 1]],
    }
    request = mock_urlopen.call_args.args[0]
    assert isinstance(request, Request)
    assert request.full_url.endswith("/v1/generate")
    assert isinstance(request.data, bytes)
    payload = json.loads(request.data)
    assert payload == {
        "algorithm": "price_network",
        "params": {"n": 3, "m": 1, "c": None, "gamma": 1.0, "seed": 42},
        "directed": True,
    }


@patch("app.adapters.graph_tool_adapter.urlopen")
def test_rejects_malformed_sidecar_graph(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _response({"nodes": [0, 1], "edges": [[0, 2]], "directed": False})

    with pytest.raises(GraphBackendError, match="invalid response"):
        graph_tool_adapter.generate_triangulation(points=[[0, 0], [1, 0], [0, 1]])


@patch("app.adapters.graph_tool_adapter.urlopen", side_effect=URLError("connection refused"))
def test_reports_unavailable_sidecar(_mock_urlopen: MagicMock) -> None:
    with pytest.raises(GraphBackendError) as error:
        graph_tool_adapter.generate_price_network(n=3)

    assert error.value.status_code == 503


@patch("app.adapters.graph_tool_adapter.urlopen")
def test_sidecar_health_reports_status(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _response({"status": "ok"})

    assert graph_tool_adapter.sidecar_health() is True
