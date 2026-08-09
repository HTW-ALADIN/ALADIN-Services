from __future__ import annotations

from typing import Literal

import networkx as nx

from app.domain import GeneratedGraph


def generate_barabasi_albert(*, n: int, m: int, seed: int | None = None) -> GeneratedGraph:
    if seed is None:
        graph = nx.barabasi_albert_graph(n=n, m=m)
    else:
        graph = nx.barabasi_albert_graph(n=n, m=m, seed=seed)

    return _generated_graph(graph)


def generate_erdos_renyi_gnp(
    *,
    n: int,
    p: float,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    graph = nx.gnp_random_graph(n=n, p=p, seed=seed, directed=directed)
    return _generated_graph(graph)


def generate_erdos_renyi_gnm(
    *,
    n: int,
    m: int,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    graph = nx.gnm_random_graph(n=n, m=m, seed=seed, directed=directed)
    return _generated_graph(graph)


def generate_watts_strogatz(
    *,
    n: int,
    k: int,
    p: float,
    seed: int | None = None,
    variant: Literal["standard", "connected"] = "standard",
    tries: int | None = None,
) -> GeneratedGraph:
    if variant == "connected":
        graph = nx.connected_watts_strogatz_graph(n=n, k=k, p=p, tries=tries or 100, seed=seed)
    else:
        graph = nx.watts_strogatz_graph(n=n, k=k, p=p, seed=seed)

    return _generated_graph(graph)


def generate_configuration_model(
    *,
    sequence: list[int],
    variant: Literal["configuration", "havel_hakimi", "expected_degree"],
    seed: int | None = None,
    selfloops: bool = True,
) -> GeneratedGraph:
    if variant == "havel_hakimi":
        graph = nx.havel_hakimi_graph(sequence)
    elif variant == "expected_degree":
        graph = nx.expected_degree_graph(sequence, seed=seed, selfloops=selfloops)
    else:
        graph = nx.configuration_model(sequence, seed=seed)
    return _generated_graph(graph)


def generate_stochastic_block_model(
    *,
    sizes: list[int],
    p: list[list[float]],
    seed: int | None = None,
    directed: bool = False,
    selfloops: bool = False,
) -> GeneratedGraph:
    graph = nx.stochastic_block_model(
        sizes=sizes,
        p=p,
        seed=seed,
        directed=directed,
        selfloops=selfloops,
    )
    return _generated_graph(graph)


def generate_random_regular(*, d: int, n: int, seed: int | None = None) -> GeneratedGraph:
    return _generated_graph(nx.random_regular_graph(d=d, n=n, seed=seed))


def generate_random_geometric(
    *,
    n: int,
    radius: float,
    dim: int = 2,
    p: float = 2.0,
    seed: int | None = None,
    variant: Literal["random_geometric", "soft_random_geometric"] = "random_geometric",
) -> GeneratedGraph:
    generator = nx.soft_random_geometric_graph if variant == "soft_random_geometric" else nx.random_geometric_graph
    return _generated_graph(generator(n=n, radius=radius, dim=dim, p=p, seed=seed))


def generate_classic_deterministic(
    *,
    shape: Literal["complete", "star", "wheel", "path", "cycle", "grid", "hypercube", "lattice"],
    n: int | None = None,
    rows: int | None = None,
    cols: int | None = None,
) -> GeneratedGraph:
    if shape in {"grid", "lattice"}:
        assert rows is not None and cols is not None
        graph = nx.grid_2d_graph(rows, cols, periodic=shape == "lattice")
    else:
        assert n is not None
        if shape == "complete":
            graph = nx.complete_graph(n)
        elif shape == "star":
            graph = nx.star_graph(n - 1)
        elif shape == "wheel":
            graph = nx.wheel_graph(n)
        elif shape == "path":
            graph = nx.path_graph(n)
        elif shape == "cycle":
            graph = nx.cycle_graph(n)
        else:
            graph = nx.hypercube_graph(n)
    return _generated_graph(graph)


def generate_named_graph(*, name: Literal["petersen", "chvatal", "tutte", "karate_club"]) -> GeneratedGraph:
    if name == "petersen":
        graph = nx.petersen_graph()
    elif name == "chvatal":
        graph = nx.chvatal_graph()
    elif name == "tutte":
        graph = nx.tutte_graph()
    else:
        graph = nx.karate_club_graph()
    return _generated_graph(graph)


def generate_random_tree(
    *,
    n: int,
    variant: Literal["random_labeled", "random_powerlaw"],
    gamma: float | None = None,
    seed: int | None = None,
    tries: int = 100,
) -> GeneratedGraph:
    if variant == "random_powerlaw":
        graph = nx.random_powerlaw_tree(n=n, gamma=gamma or 3.0, seed=seed, tries=tries)
    else:
        graph = nx.random_labeled_tree(n=n, seed=seed)
    return _generated_graph(graph)


def generate_random_bipartite(
    *,
    n1: int,
    n2: int,
    p: float | None = None,
    m: int | None = None,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    if m is not None:
        graph = nx.bipartite.gnmk_random_graph(n=n1, m=n2, k=m, seed=seed, directed=directed)
    else:
        assert p is not None
        graph = nx.bipartite.random_graph(n=n1, m=n2, p=p, seed=seed, directed=directed)
    return _generated_graph(graph)


def generate_community_clustered(
    *,
    variant: Literal["planted_partition", "gaussian_random_partition", "lfr", "relaxed_caveman"],
    n: int | None = None,
    l: int | None = None,  # noqa: E741 - matches the NetworkX API
    k: int | None = None,
    s: float | None = None,
    v: float | None = None,
    p: float | None = None,
    p_intra: float | None = None,
    p_inter: float | None = None,
    tau1: float | None = None,
    tau2: float | None = None,
    mu: float | None = None,
    average_degree: int | None = None,
    min_degree: int | None = None,
    max_degree: int | None = None,
    min_community: int | None = None,
    max_community: int | None = None,
    seed: int | None = None,
    directed: bool = False,
) -> GeneratedGraph:
    if variant == "planted_partition":
        assert l is not None and k is not None and p_intra is not None and p_inter is not None
        graph = nx.planted_partition_graph(l=l, k=k, p_in=p_intra, p_out=p_inter, seed=seed, directed=directed)
    elif variant == "gaussian_random_partition":
        assert n is not None and s is not None and v is not None and p_intra is not None and p_inter is not None
        graph = nx.gaussian_random_partition_graph(
            n=n,
            s=s,
            v=v,
            p_in=p_intra,
            p_out=p_inter,
            seed=seed,
            directed=directed,
        )
    elif variant == "relaxed_caveman":
        assert l is not None and k is not None and p is not None
        graph = nx.relaxed_caveman_graph(l=l, k=k, p=p, seed=seed)
    else:
        assert n is not None and tau1 is not None and tau2 is not None and mu is not None
        graph = nx.LFR_benchmark_graph(
            n=n,
            tau1=tau1,
            tau2=tau2,
            mu=mu,
            average_degree=average_degree,
            min_degree=min_degree,
            max_degree=max_degree,
            min_community=min_community,
            max_community=max_community,
            seed=seed,
        )
    return _generated_graph(graph)


def generate_chung_lu(
    *, degree_sequence: list[float], seed: int | None = None, selfloops: bool = True
) -> GeneratedGraph:
    return _generated_graph(nx.expected_degree_graph(degree_sequence, seed=seed, selfloops=selfloops))


def generate_kleinberg_small_world(
    *, n: int, p: int = 1, q: int = 1, r: int = 2, dim: int = 2, seed: int | None = None
) -> GeneratedGraph:
    return _generated_graph(nx.navigable_small_world_graph(n=n, p=p, q=q, r=r, dim=dim, seed=seed))


def generate_powerlaw_cluster(*, n: int, m: int, p: float, seed: int | None = None) -> GeneratedGraph:
    return _generated_graph(nx.powerlaw_cluster_graph(n=n, m=m, p=p, seed=seed))


def generate_geometric_threshold(
    *,
    variant: Literal["waxman", "geographical_threshold"],
    n: int,
    beta: float | None = None,
    alpha: float | None = None,
    theta: float | None = None,
    dim: int = 2,
    seed: int | None = None,
) -> GeneratedGraph:
    if variant == "waxman":
        assert beta is not None and alpha is not None
        graph = nx.waxman_graph(n=n, beta=beta, alpha=alpha, seed=seed)
    else:
        assert theta is not None
        graph = nx.geographical_threshold_graph(n=n, theta=theta, dim=dim, seed=seed)
    return _generated_graph(graph)


def generate_internet_as(*, n: int, seed: int | None = None) -> GeneratedGraph:
    return _generated_graph(nx.random_internet_as_graph(n=n, seed=seed))


def _generated_graph(graph: nx.Graph[int]) -> GeneratedGraph:
    return GeneratedGraph(
        graph=graph,
        num_nodes=int(graph.number_of_nodes()),
        num_edges=int(graph.number_of_edges()),
        directed=bool(graph.is_directed()),
    )
