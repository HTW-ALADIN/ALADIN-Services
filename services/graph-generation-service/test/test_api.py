from unittest.mock import MagicMock, patch
from uuid import UUID

import networkx
import pytest
from fastapi.testclient import TestClient

from app.main import GRAPH_STORE, app
from app.routing import ADAPTERS

client = TestClient(app)


def setup_function() -> None:
    GRAPH_STORE.clear()


def test_rejects_invalid_backend_for_algorithm() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "forest_fire",
            "backend": "networkx",
            "params": {"n": 100, "fw_prob": 0.3},
            "output": {"format": "edge_list"},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert any(error["name"] == "backend" for error in response.json()["invalidParams"])


def test_rejects_explicit_empty_backend() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "",
            "params": {"n": 500, "m": 3},
        },
    )

    assert response.status_code == 400
    assert any(error["name"] == "backend" for error in response.json()["invalidParams"])


def test_rejects_missing_backend_parameter() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkx",
            "params": {"n": 500},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert any(error["name"].endswith("m") for error in response.json()["invalidParams"])


@patch("app.adapters.networkx_adapter.nx.barabasi_albert_graph")
def test_routes_barabasi_albert_to_networkx(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkx",
            "params": {"n": 500, "m": 3, "seed": 42},
            "output": {"format": "edge_list", "directed": False},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=500, m=3, seed=42)


@patch("app.adapters.igraph_adapter.Graph.Barabasi")
def test_routes_barabasi_albert_to_igraph(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "igraph",
            "params": {"n": 500, "m": 3, "power": 1.5, "zero_appeal": 1.0},
            "output": {"format": "edge_list", "directed": False},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=500, m=3, power=1.5, zero_appeal=1.0, directed=False)


@patch("app.adapters.networkit_adapter.BarabasiAlbertGenerator")
def test_routes_barabasi_albert_to_networkit(mock_generator: MagicMock) -> None:
    instance = mock_generator.return_value
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkit",
            "params": {"k": 3, "nMax": 500, "n0": 4, "batagelj": True},
        },
    )

    assert response.status_code == 201
    mock_generator.assert_called_once_with(k=3, nMax=500, n0=4, batagelj=True)
    instance.generate.assert_called_once_with()


@patch("app.adapters.igraph_adapter.Graph.Forest_Fire")
def test_routes_forest_fire_to_igraph(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "forest_fire",
            "backend": "igraph",
            "params": {"n": 100, "fw_prob": 0.3, "bw_factor": 0.1, "ambs": 2},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, fw_prob=0.3, bw_factor=0.1, ambs=2, directed=True)


@patch("app.adapters.networkx_adapter.nx.gnp_random_graph")
def test_routes_erdos_renyi_gnp_to_networkx(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnp",
            "backend": "networkx",
            "params": {"n": 100, "p": 0.2, "seed": 42},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, p=0.2, seed=42, directed=True)


@patch("app.adapters.igraph_adapter.Graph.Erdos_Renyi")
def test_routes_erdos_renyi_gnp_to_igraph(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnp",
            "backend": "igraph",
            "params": {"n": 100, "p": 0.2, "loops": True},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, p=0.2, directed=True, loops=True)


@patch("app.adapters.networkit_adapter.ErdosRenyiGenerator")
def test_routes_erdos_renyi_gnp_to_networkit(mock_generator: MagicMock) -> None:
    instance = mock_generator.return_value
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnp",
            "backend": "networkit",
            "params": {"n": 100, "p": 0.2, "selfLoops": True},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 201
    mock_generator.assert_called_once_with(nNodes=100, prob=0.2, directed=True, selfLoops=True)
    instance.generate.assert_called_once_with()


@patch("app.adapters.networkx_adapter.nx.gnm_random_graph")
def test_routes_erdos_renyi_gnm_to_networkx(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnm",
            "backend": "networkx",
            "params": {"n": 20, "m": 200, "seed": 42},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=20, m=200, seed=42, directed=True)


@patch("app.adapters.igraph_adapter.Graph.Erdos_Renyi")
def test_routes_erdos_renyi_gnm_to_igraph(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnm",
            "backend": "igraph",
            "params": {"n": 100, "m": 200},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, m=200, directed=False)


def test_rejects_invalid_erdos_renyi_probability() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnp",
            "backend": "networkx",
            "params": {"n": 100, "p": 1.1},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_rejects_erdos_renyi_gnm_edge_count_above_capacity() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnm",
            "backend": "networkx",
            "params": {"n": 4, "m": 7},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["invalidParams"] == [
        {
            "name": "params.m",
            "reason": "Value error, m must not exceed 6 for the requested graph",
        }
    ]


def test_erdos_renyi_gnm_accepts_empty_graph() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "erdos_renyi_gnm",
            "backend": "networkx",
            "params": {"n": 4, "m": 0, "seed": 42},
        },
    )

    assert response.status_code == 201
    assert response.json()["metadata"]["numEdges"] == 0


@patch("app.adapters.networkx_adapter.nx.watts_strogatz_graph")
def test_routes_standard_watts_strogatz_to_networkx(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {"n": 100, "k": 4, "p": 0.2, "seed": 42},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, k=4, p=0.2, seed=42)


@patch("app.adapters.networkx_adapter.nx.connected_watts_strogatz_graph")
def test_routes_connected_watts_strogatz_to_networkx(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {
                "n": 100,
                "k": 4,
                "p": 0.2,
                "seed": 42,
                "variant": "connected",
                "tries": 25,
            },
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(n=100, k=4, p=0.2, tries=25, seed=42)


@patch("app.adapters.igraph_adapter.Graph.Watts_Strogatz")
def test_routes_watts_strogatz_to_igraph(mock_generate: MagicMock) -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "igraph",
            "params": {"dim": 2, "size": 10, "nei": 2, "p": 0.2},
        },
    )

    assert response.status_code == 201
    mock_generate.assert_called_once_with(dim=2, size=10, nei=2, p=0.2)


@patch("app.adapters.networkit_adapter.WattsStrogatzGenerator")
def test_routes_watts_strogatz_to_networkit(mock_generator: MagicMock) -> None:
    instance = mock_generator.return_value
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkit",
            "params": {"n": 100, "nNeighbors": 4, "p": 0.2},
        },
    )

    assert response.status_code == 201
    mock_generator.assert_called_once_with(nNodes=100, nNeighbors=4, p=0.2)
    instance.generate.assert_called_once_with()


def test_rejects_invalid_watts_strogatz_probability() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "igraph",
            "params": {"dim": 1, "size": 20, "nei": 2, "p": 1.1},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_rejects_directed_watts_strogatz_output() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {"n": 20, "k": 4, "p": 0.2},
            "output": {"directed": True},
        },
    )

    assert response.status_code == 400
    assert response.json()["invalidParams"][0]["name"] == "output.directed"


def test_rejects_tries_for_standard_watts_strogatz() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {"n": 20, "k": 4, "p": 0.2, "tries": 10},
        },
    )

    assert response.status_code == 400
    assert response.json()["invalidParams"][0]["name"] == "params.tries"


def test_rejects_watts_strogatz_k_above_node_count() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {"n": 20, "k": 21, "p": 0.2},
        },
    )

    assert response.status_code == 400
    assert response.json()["invalidParams"][0]["name"] == "params.k"


def test_rejects_connected_watts_strogatz_with_too_few_neighbors() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkx",
            "params": {"n": 20, "k": 1, "p": 0.2, "variant": "connected"},
        },
    )

    assert response.status_code == 400
    assert response.json()["invalidParams"][0]["name"] == "params.k"


def test_rejects_excessive_networkit_watts_strogatz_neighbors() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "watts_strogatz",
            "backend": "networkit",
            "params": {"n": 9, "nNeighbors": 4, "p": 0.2},
        },
    )

    assert response.status_code == 400
    assert response.json()["invalidParams"][0]["name"] == "params.nNeighbors"


def test_graph_resource_lifecycle() -> None:
    create_response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "forest_fire",
            "backend": "igraph",
            "params": {"n": 100, "fw_prob": 0.3},
            "output": {"format": "graphml", "labels": "uuid"},
        },
    )
    graph = create_response.json()

    assert graph["id"].startswith("grf_")
    assert graph["metadata"]["numNodes"] == 100
    assert graph["metadata"]["numEdges"] >= 0
    assert graph["_links"]["export"].endswith("?format=graphml")
    assert client.get(graph["_links"]["self"]).json() == graph
    export_response = client.get(graph["_links"]["export"])
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/graphml+xml"
    assert b"<graphml" in export_response.content
    assert client.delete(graph["_links"]["self"]).status_code == 204
    assert client.get(graph["_links"]["self"]).status_code == 404


def test_edge_list_export_from_networkx() -> None:
    create_response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkx",
            "params": {"n": 20, "m": 2, "seed": 42},
            "output": {"format": "edge_list"},
        },
    )
    resource = create_response.json()

    export_response = client.get(resource["_links"]["export"])
    exported = export_response.json()

    assert export_response.headers["content-type"] == "application/json"
    assert exported["format"] == "edge_list"
    assert len(exported["nodes"]) == resource["metadata"]["numNodes"]
    assert len(exported["edges"]) == resource["metadata"]["numEdges"]


def test_adjacency_export_uses_stable_uuid_labels() -> None:
    create_response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "igraph",
            "params": {"n": 20, "m": 2},
            "output": {"format": "adjacency", "labels": "uuid"},
        },
    )
    export_url = create_response.json()["_links"]["export"]

    first = client.get(export_url).json()
    second = client.get(export_url).json()

    assert first == second
    assert first["format"] == "adjacency"
    assert all(str(UUID(node["id"])) == node["id"] for node in first["nodes"])


def test_gml_export_from_networkit() -> None:
    create_response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkit",
            "params": {"k": 2, "nMax": 20, "n0": 4},
            "output": {"format": "gml"},
        },
    )

    export_response = client.get(create_response.json()["_links"]["export"])

    assert export_response.headers["content-type"].startswith("text/plain")
    assert export_response.text.startswith("graph [")


def test_graph6_export_round_trip() -> None:
    create_response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "networkx",
            "params": {"n": 20, "m": 2, "seed": 42},
            "output": {"format": "graph6"},
        },
    )
    resource = create_response.json()

    export_response = client.get(resource["_links"]["export"])
    decoded = networkx.from_graph6_bytes(export_response.content.strip())

    assert export_response.headers["content-type"] == "application/octet-stream"
    assert decoded.number_of_nodes() == resource["metadata"]["numNodes"]
    assert decoded.number_of_edges() == resource["metadata"]["numEdges"]


def test_rejects_incompatible_graph6_options() -> None:
    response = client.post(
        "/v1/graphs",
        json={
            "algorithm": "barabasi_albert",
            "backend": "igraph",
            "params": {"n": 20, "m": 2},
            "output": {"format": "graph6", "directed": True},
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize(
    "payload",
    [
        {"algorithm": "configuration_model", "backend": "networkx", "params": {"sequence": [2, 2, 2, 2]}},
        {"algorithm": "configuration_model", "backend": "igraph", "params": {"out": [2, 2, 2, 2]}},
        {"algorithm": "configuration_model", "backend": "networkit", "params": {"sequence": [2, 2, 2, 2]}},
        {
            "algorithm": "stochastic_block_model",
            "backend": "networkx",
            "params": {"sizes": [5, 5], "p": [[0.5, 0.1], [0.1, 0.5]]},
        },
        {
            "algorithm": "stochastic_block_model",
            "backend": "igraph",
            "params": {"n": 10, "block_sizes": [5, 5], "pref_matrix": [[0.5, 0.1], [0.1, 0.5]]},
        },
        {
            "algorithm": "stochastic_block_model",
            "backend": "networkit",
            "params": {
                "n": 10,
                "nBlocks": 2,
                "membership": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                "affinity": [[0.5, 0.1], [0.1, 0.5]],
            },
        },
        {"algorithm": "random_regular", "backend": "networkx", "params": {"n": 10, "d": 2}},
        {"algorithm": "random_regular", "backend": "igraph", "params": {"n": 10, "k": 2}},
        {"algorithm": "random_geometric", "backend": "networkx", "params": {"n": 10, "radius": 0.4}},
        {"algorithm": "random_geometric", "backend": "igraph", "params": {"n": 10, "radius": 0.4}},
        {
            "algorithm": "kronecker_rmat",
            "backend": "networkit",
            "params": {"scale": 4, "edgeFactor": 2, "a": 0.57, "b": 0.19, "c": 0.19, "d": 0.05},
        },
        {"algorithm": "classic_deterministic", "backend": "networkx", "params": {"shape": "wheel", "n": 8}},
        {"algorithm": "classic_deterministic", "backend": "igraph", "params": {"shape": "wheel", "n": 8}},
        {"algorithm": "named_graph", "backend": "networkx", "params": {"name": "petersen"}},
        {"algorithm": "named_graph", "backend": "igraph", "params": {"name": "petersen"}},
        {"algorithm": "random_tree", "backend": "networkx", "params": {"n": 10, "variant": "random_labeled"}},
        {"algorithm": "random_tree", "backend": "igraph", "params": {"n": 10, "variant": "tree_game"}},
        {"algorithm": "random_bipartite", "backend": "networkx", "params": {"n1": 5, "n2": 5, "p": 0.2}},
        {"algorithm": "random_bipartite", "backend": "igraph", "params": {"n1": 5, "n2": 5, "p": 0.2}},
        {
            "algorithm": "community_clustered",
            "backend": "networkx",
            "params": {"variant": "planted_partition", "l": 2, "k": 5, "pIntra": 0.5, "pInter": 0.1},
        },
        {
            "algorithm": "community_clustered",
            "backend": "networkit",
            "params": {"variant": "clustered_random", "n": 10, "k": 2, "pIntra": 0.5, "pInter": 0.1},
        },
        {"algorithm": "hyperbolic", "backend": "networkit", "params": {"n": 20}},
        {"algorithm": "chung_lu", "backend": "networkx", "params": {"degreeSequence": [2, 2, 2, 2]}},
        {"algorithm": "chung_lu", "backend": "networkit", "params": {"degreeSequence": [2, 2, 2, 2]}},
        {"algorithm": "static_fitness", "backend": "igraph", "params": {"m": 3, "fitness_out": [1, 1, 1, 1]}},
        {
            "algorithm": "growing_attachment",
            "backend": "igraph",
            "params": {"variant": "growing_random", "n": 10, "m": 2},
        },
        {"algorithm": "kleinberg_small_world", "backend": "networkx", "params": {"n": 4}},
        {"algorithm": "powerlaw_cluster", "backend": "networkx", "params": {"n": 10, "m": 2, "p": 0.3}},
        {
            "algorithm": "geometric_threshold",
            "backend": "networkx",
            "params": {"variant": "waxman", "n": 10, "beta": 0.4, "alpha": 0.1},
        },
        {"algorithm": "duplication_divergence", "backend": "networkx", "params": {"n": 20}},
    ],
)
def test_all_remaining_spec_a_backends_generate(payload: dict[str, object]) -> None:
    response = client.post("/v1/graphs", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "completed"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "algorithm": "configuration_model",
            "backend": "networkx",
            "params": {"sequence": [2, 2, 2, 2], "variant": "havel_hakimi"},
        },
        {
            "algorithm": "configuration_model",
            "backend": "networkit",
            "params": {"sequence": [2, 2, 2, 2], "variant": "edge_switching"},
        },
        {
            "algorithm": "configuration_model",
            "backend": "networkx",
            "params": {"sequence": [2, 2, 2, 2], "variant": "expected_degree"},
        },
        {
            "algorithm": "random_geometric",
            "backend": "networkx",
            "params": {"n": 10, "radius": 0.4, "variant": "soft_random_geometric"},
        },
        {
            "algorithm": "community_clustered",
            "backend": "networkx",
            "params": {"variant": "relaxed_caveman", "l": 2, "k": 5, "p": 0.1},
        },
        {
            "algorithm": "community_clustered",
            "backend": "networkx",
            "params": {
                "variant": "gaussian_random_partition",
                "n": 30,
                "s": 5,
                "v": 1,
                "pIntra": 0.5,
                "pInter": 0.05,
            },
        },
        {
            "algorithm": "community_clustered",
            "backend": "networkx",
            "params": {
                "variant": "lfr",
                "n": 100,
                "tau1": 3.0,
                "tau2": 1.5,
                "mu": 0.1,
                "averageDegree": 5,
                "maxDegree": 20,
                "minCommunity": 10,
                "maxCommunity": 30,
                "seed": 42,
            },
        },
        {
            "algorithm": "community_clustered",
            "backend": "networkit",
            "params": {
                "variant": "lfr",
                "n": 100,
                "tau1": 3.0,
                "tau2": 1.5,
                "mu": 0.1,
                "averageDegree": 5,
                "maxDegree": 20,
                "minCommunity": 10,
                "maxCommunity": 30,
            },
        },
        {
            "algorithm": "random_tree",
            "backend": "networkx",
            "params": {"n": 20, "variant": "random_powerlaw", "gamma": 3.0, "seed": 0, "tries": 1000},
        },
        {"algorithm": "random_bipartite", "backend": "igraph", "params": {"n1": 5, "n2": 5, "m": 8}},
        {
            "algorithm": "static_fitness",
            "backend": "igraph",
            "params": {"variant": "static_power_law", "n": 20, "m": 20, "exponent_out": 2.5},
        },
        {
            "algorithm": "growing_attachment",
            "backend": "igraph",
            "params": {
                "variant": "preference",
                "n": 20,
                "type_dist": [0.5, 0.5],
                "pref_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
        },
        {
            "algorithm": "growing_attachment",
            "backend": "igraph",
            "params": {
                "variant": "establishment",
                "n": 20,
                "k": 2,
                "type_dist": [0.5, 0.5],
                "pref_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
        },
        {
            "algorithm": "growing_attachment",
            "backend": "igraph",
            "params": {"variant": "recent_degree", "n": 20, "m": 2, "window": 5, "power": 1.2},
        },
        {
            "algorithm": "growing_attachment",
            "backend": "igraph",
            "params": {
                "variant": "asymmetric_preference",
                "n": 20,
                "type_dist_matrix": [[0.25, 0.25], [0.25, 0.25]],
                "pref_matrix": [[0.8, 0.2], [0.2, 0.8]],
            },
            "output": {"directed": True},
        },
        {
            "algorithm": "geometric_threshold",
            "backend": "networkx",
            "params": {"variant": "geographical_threshold", "n": 10, "theta": 1.0},
        },
    ],
)
def test_multi_variant_generators(payload: dict[str, object]) -> None:
    assert client.post("/v1/graphs", json=payload).status_code == 201


@pytest.mark.parametrize(
    ("payload", "invalid_name"),
    [
        (
            {"algorithm": "random_bipartite", "backend": "networkx", "params": {"n1": 5, "n2": 5}},
            "params",
        ),
        (
            {"algorithm": "random_regular", "backend": "networkx", "params": {"n": 5, "d": 3}},
            "params.d",
        ),
        (
            {
                "algorithm": "stochastic_block_model",
                "backend": "networkx",
                "params": {"sizes": [5, 5], "p": [[0.5], [0.1]]},
            },
            "params.p",
        ),
        (
            {
                "algorithm": "kronecker_rmat",
                "backend": "networkit",
                "params": {"scale": 4, "edgeFactor": 2, "a": 0.5, "b": 0.2, "c": 0.2, "d": 0.2},
            },
            "params",
        ),
    ],
)
def test_new_algorithm_validation_uses_problem_details(payload: dict[str, object], invalid_name: str) -> None:
    response = client.post("/v1/graphs", json=payload)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["invalidParams"][0]["name"] == invalid_name


def test_openapi_contains_only_specified_routes() -> None:
    schema = app.openapi()

    assert set(schema["paths"]) == {
        "/v1/algorithms",
        "/v1/graphs",
        "/v1/graphs/{graphId}",
    }
    for path in schema["paths"].values():
        for operation in path.values():
            assert "422" not in operation["responses"]


def test_catalog_exposes_complete_two_level_spec_a_union() -> None:
    catalog = client.get("/v1/algorithms").json()
    algorithms = catalog["algorithms"]
    components = app.openapi()["components"]["schemas"]

    assert len(algorithms) == 42
    assert len({entry["algorithm"] for entry in algorithms}) == 23
    for algorithm in {entry["algorithm"] for entry in algorithms}:
        backends = [entry for entry in algorithms if entry["algorithm"] == algorithm]
        if len(backends) > 1:
            request_name = "".join(part.title() for part in algorithm.split("_")) + "Request"
            assert components[request_name]["discriminator"]["propertyName"] == "backend"
            assert len({entry["paramsSchema"] for entry in backends}) == len(backends)


def test_adapter_registry_matches_catalog() -> None:
    algorithms = client.get("/v1/algorithms").json()["algorithms"]

    assert set(ADAPTERS) == {(entry["algorithm"], entry["backend"]) for entry in algorithms}
