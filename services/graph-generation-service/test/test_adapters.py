import igraph
import networkit
import networkx

from app.adapters import igraph_adapter, networkit_adapter, networkx_adapter


def test_networkx_barabasi_albert_generates_real_graph() -> None:
    generated = networkx_adapter.generate_barabasi_albert(n=20, m=2, seed=42)

    assert isinstance(generated.graph, networkx.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges > 0
    assert generated.directed is False


def test_igraph_barabasi_albert_generates_real_graph() -> None:
    generated = igraph_adapter.generate_barabasi_albert(n=20, m=2)

    assert isinstance(generated.graph, igraph.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges > 0
    assert generated.directed is False


def test_igraph_forest_fire_generates_real_graph() -> None:
    generated = igraph_adapter.generate_forest_fire(n=20, fw_prob=0.3)

    assert isinstance(generated.graph, igraph.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges >= 0
    assert generated.directed is False


def test_networkit_barabasi_albert_generates_real_graph() -> None:
    generated = networkit_adapter.generate_barabasi_albert(k=2, n_max=20, n0=4)

    assert isinstance(generated.graph, networkit.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges > 0
    assert generated.directed is False


def test_networkx_erdos_renyi_gnp_generates_real_graph() -> None:
    generated = networkx_adapter.generate_erdos_renyi_gnp(n=20, p=0.3, seed=42, directed=True)

    assert isinstance(generated.graph, networkx.DiGraph)
    assert generated.num_nodes == 20
    assert generated.num_edges >= 0
    assert generated.directed is True


def test_igraph_erdos_renyi_gnp_generates_real_graph() -> None:
    generated = igraph_adapter.generate_erdos_renyi_gnp(n=20, p=0.3, directed=True)

    assert isinstance(generated.graph, igraph.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges >= 0
    assert generated.directed is True


def test_networkit_erdos_renyi_gnp_generates_real_graph() -> None:
    generated = networkit_adapter.generate_erdos_renyi_gnp(n=20, p=0.3, directed=True)

    assert isinstance(generated.graph, networkit.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges >= 0
    assert generated.directed is True


def test_networkx_erdos_renyi_gnm_generates_real_graph() -> None:
    generated = networkx_adapter.generate_erdos_renyi_gnm(n=20, m=30, seed=42, directed=True)

    assert isinstance(generated.graph, networkx.DiGraph)
    assert generated.num_nodes == 20
    assert generated.num_edges == 30
    assert generated.directed is True


def test_igraph_erdos_renyi_gnm_generates_real_graph() -> None:
    generated = igraph_adapter.generate_erdos_renyi_gnm(n=20, m=30)

    assert isinstance(generated.graph, igraph.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges == 30
    assert generated.directed is False


def test_networkx_watts_strogatz_generates_real_graph() -> None:
    generated = networkx_adapter.generate_watts_strogatz(n=20, k=4, p=0.2, seed=42)

    assert isinstance(generated.graph, networkx.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges == 40
    assert generated.directed is False


def test_networkx_connected_watts_strogatz_generates_connected_graph() -> None:
    generated = networkx_adapter.generate_watts_strogatz(
        n=20,
        k=4,
        p=0.2,
        seed=42,
        variant="connected",
    )

    assert isinstance(generated.graph, networkx.Graph)
    assert networkx.is_connected(generated.graph)
    assert generated.num_nodes == 20
    assert generated.directed is False


def test_igraph_watts_strogatz_generates_real_graph() -> None:
    generated = igraph_adapter.generate_watts_strogatz(dim=1, size=20, nei=2, p=0.2)

    assert isinstance(generated.graph, igraph.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges == 40
    assert generated.directed is False


def test_networkit_watts_strogatz_generates_real_graph() -> None:
    generated = networkit_adapter.generate_watts_strogatz(n=20, n_neighbors=2, p=0.2)

    assert isinstance(generated.graph, networkit.Graph)
    assert generated.num_nodes == 20
    assert generated.num_edges == 40
    assert generated.directed is False
