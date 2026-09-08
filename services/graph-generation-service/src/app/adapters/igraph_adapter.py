from __future__ import annotations

from typing import Literal

from igraph import Graph

from app.domain import GeneratedGraph


def generate_barabasi_albert(
    *,
    n: int,
    m: int,
    power: float = 1.0,
    zero_appeal: float = 1.0,
    directed: bool = False,
) -> GeneratedGraph:
    graph = Graph.Barabasi(n=n, m=m, power=power, zero_appeal=zero_appeal, directed=directed)
    return _generated_graph(graph)


def generate_forest_fire(
    *,
    n: int,
    fw_prob: float,
    bw_factor: float = 0.0,
    ambs: int = 1,
    directed: bool = False,
) -> GeneratedGraph:
    graph = Graph.Forest_Fire(n=n, fw_prob=fw_prob, bw_factor=bw_factor, ambs=ambs, directed=directed)
    return _generated_graph(graph)


def generate_erdos_renyi_gnp(
    *,
    n: int,
    p: float,
    loops: bool = False,
    directed: bool = False,
) -> GeneratedGraph:
    graph = Graph.Erdos_Renyi(n=n, p=p, directed=directed, loops=loops)
    return _generated_graph(graph)


def generate_erdos_renyi_gnm(
    *,
    n: int,
    m: int,
    directed: bool = False,
) -> GeneratedGraph:
    graph = Graph.Erdos_Renyi(n=n, m=m, directed=directed)
    return _generated_graph(graph)


def generate_watts_strogatz(*, dim: int, size: int, nei: int, p: float) -> GeneratedGraph:
    graph = Graph.Watts_Strogatz(dim=dim, size=size, nei=nei, p=p)
    return _generated_graph(graph)


def generate_configuration_model(
    *,
    out: list[int],
    in_: list[int] | None = None,
    method: Literal[
        "configuration",
        "fast_heur_simple",
        "configuration_simple",
        "edge_switching_simple",
        "vl",
    ] = "configuration",
) -> GeneratedGraph:
    if in_ is None:
        graph = Graph.Degree_Sequence(out=out, method=method)
    else:
        graph = Graph.Degree_Sequence(out=out, in_=in_, method=method)
    return _generated_graph(graph)


def generate_stochastic_block_model(
    *, n: int, pref_matrix: list[list[float]], block_sizes: list[int], directed: bool = False
) -> GeneratedGraph:
    del n
    return _generated_graph(Graph.SBM(pref_matrix=pref_matrix, block_sizes=block_sizes, directed=directed))


def generate_random_regular(*, n: int, k: int, directed: bool = False, multiple: bool = False) -> GeneratedGraph:
    return _generated_graph(Graph.K_Regular(n=n, k=k, directed=directed, multiple=multiple))


def generate_random_geometric(*, n: int, radius: float, torus: bool = False) -> GeneratedGraph:
    return _generated_graph(Graph.GRG(n=n, radius=radius, torus=torus))


def generate_classic_deterministic(
    *,
    shape: Literal["complete", "star", "wheel", "path", "cycle", "grid", "hypercube", "lattice"],
    n: int | None = None,
    rows: int | None = None,
    cols: int | None = None,
) -> GeneratedGraph:
    if shape in {"grid", "lattice"}:
        if not (rows is not None and cols is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Lattice(dim=[rows, cols], circular=shape == "lattice")
    else:
        if not (n is not None):
            raise ValueError("required graph parameters are missing")
        if shape == "complete":
            graph = Graph.Full(n=n)
        elif shape == "star":
            if n == 1:
                graph = Graph(n=1)
            else:
                graph = Graph.Star(n=n)
        elif shape == "wheel":
            graph = Graph.Ring(n=n - 1)
            graph.add_vertex()
            graph.add_edges((n - 1, node) for node in range(n - 1))
        elif shape == "path":
            graph = Graph.Ring(n=n, circular=False)
        elif shape == "cycle":
            graph = Graph.Ring(n=n)
        else:
            graph = Graph.Hypercube(n=n)
    return _generated_graph(graph)


def generate_named_graph(*, name: Literal["petersen", "chvatal", "tutte", "karate_club"]) -> GeneratedGraph:
    igraph_names = {"petersen": "Petersen", "chvatal": "Chvatal", "tutte": "Tutte", "karate_club": "Zachary"}
    return _generated_graph(Graph.Famous(igraph_names[name]))


def generate_random_tree(
    *,
    n: int,
    variant: Literal["tree_game"] = "tree_game",
    method: Literal["lerw", "prufer", "random"] = "lerw",
    directed: bool = False,
) -> GeneratedGraph:
    del variant
    return _generated_graph(Graph.Tree_Game(n=n, method=method, directed=directed))


def generate_random_bipartite(
    *, n1: int, n2: int, p: float | None = None, m: int | None = None, directed: bool = False
) -> GeneratedGraph:
    return _generated_graph(Graph.Random_Bipartite(n1=n1, n2=n2, p=p, m=m, directed=directed))


def generate_static_fitness(
    *,
    variant: Literal["static_fitness", "static_power_law"],
    m: int,
    fitness_out: list[float] | None = None,
    fitness_in: list[float] | None = None,
    n: int | None = None,
    exponent_out: float | None = None,
    exponent_in: float | None = None,
) -> GeneratedGraph:
    if variant == "static_fitness":
        if not (fitness_out is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Static_Fitness(m=m, fitness_out=fitness_out, fitness_in=fitness_in)
    else:
        if not (n is not None and exponent_out is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Static_Power_Law(
            n=n,
            m=m,
            exponent_out=exponent_out,
            exponent_in=-1 if exponent_in is None else exponent_in,
        )
    return _generated_graph(graph)


def generate_growing_attachment(
    *,
    variant: Literal["growing_random", "establishment", "preference", "asymmetric_preference", "recent_degree"],
    n: int,
    directed: bool,
    m: int | None = None,
    power: float | None = None,
    k: int | None = None,
    type_dist: list[float] | None = None,
    type_dist_matrix: list[list[float]] | None = None,
    pref_matrix: list[list[float]] | None = None,
    window: int | None = None,
    citation: bool = False,
    outpref: bool = False,
    loops: bool = False,
) -> GeneratedGraph:
    if variant == "growing_random":
        if not (m is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Growing_Random(n=n, m=m, directed=directed, citation=citation)
    elif variant == "establishment":
        if not (k is not None and type_dist is not None and pref_matrix is not None):
            raise ValueError("required graph parameters are missing")
        type_weights = [max(1, round(weight * 1_000_000)) for weight in type_dist]
        graph = Graph.Establishment(n=n, k=k, type_dist=type_weights, pref_matrix=pref_matrix, directed=directed)
    elif variant == "preference":
        if not (type_dist is not None and pref_matrix is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Preference(n=n, type_dist=type_dist, pref_matrix=pref_matrix, directed=directed, loops=loops)
    elif variant == "asymmetric_preference":
        if not (type_dist_matrix is not None and pref_matrix is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Asymmetric_Preference(
            n=n,
            type_dist_matrix=type_dist_matrix,
            pref_matrix=pref_matrix,
            loops=loops,
        )
    else:
        if not (m is not None and window is not None):
            raise ValueError("required graph parameters are missing")
        graph = Graph.Recent_Degree(
            n=n,
            m=m,
            window=window,
            outpref=outpref,
            directed=directed,
            power=1.0 if power is None else power,
        )
    return _generated_graph(graph)


def _generated_graph(graph: Graph) -> GeneratedGraph:
    return GeneratedGraph(
        graph=graph,
        num_nodes=int(graph.vcount()),
        num_edges=int(graph.ecount()),
        directed=bool(graph.is_directed()),
    )
