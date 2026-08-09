from __future__ import annotations

from networkit import Graph
from networkit.generators import BarabasiAlbertGenerator as _NetworKitBarabasiAlbertGenerator
from networkit.generators import ChungLuGenerator as _NetworKitChungLuGenerator
from networkit.generators import ClusteredRandomGraphGenerator as _NetworKitClusteredRandomGraphGenerator
from networkit.generators import EdgeSwitchingMarkovChainGenerator as _NetworKitEdgeSwitchingGenerator
from networkit.generators import ErdosRenyiGenerator as _NetworKitErdosRenyiGenerator
from networkit.generators import HavelHakimiGenerator as _NetworKitHavelHakimiGenerator
from networkit.generators import HyperbolicGenerator as _NetworKitHyperbolicGenerator
from networkit.generators import LFRGenerator as _NetworKitLFRGenerator
from networkit.generators import RmatGenerator as _NetworKitRmatGenerator
from networkit.generators import WattsStrogatzGenerator as _NetworKitWattsStrogatzGenerator

from app.domain import GeneratedGraph


class BarabasiAlbertGenerator:
    def __init__(self, *, k: int, nMax: int, n0: int, batagelj: bool = True) -> None:
        self._generator = _NetworKitBarabasiAlbertGenerator(k, nMax, n0, batagelj)

    def generate(self) -> Graph:
        return self._generator.generate()


class ErdosRenyiGenerator:
    def __init__(
        self,
        *,
        nNodes: int,
        prob: float,
        directed: bool = False,
        selfLoops: bool = False,
    ) -> None:
        self._generator = _NetworKitErdosRenyiGenerator(nNodes, prob, directed, selfLoops)

    def generate(self) -> Graph:
        return self._generator.generate()


class WattsStrogatzGenerator:
    def __init__(self, *, nNodes: int, nNeighbors: int, p: float) -> None:
        self._generator = _NetworKitWattsStrogatzGenerator(nNodes, nNeighbors, p)

    def generate(self) -> Graph:
        return self._generator.generate()


class HavelHakimiGenerator:
    def __init__(self, *, sequence: list[int], ignoreIfRealizable: bool = True) -> None:
        self._generator = _NetworKitHavelHakimiGenerator(sequence, ignoreIfRealizable)

    def generate(self) -> Graph:
        return self._generator.generate()


class EdgeSwitchingMarkovChainGenerator:
    def __init__(
        self,
        *,
        degreeSequence: list[int],
        ignoreIfNotRealizable: bool = False,
        numSwitchesPerEdge: int = 10,
    ) -> None:
        self._generator = _NetworKitEdgeSwitchingGenerator(
            degreeSequence,
            ignoreIfNotRealizable,
            numSwitchesPerEdge,
        )

    def generate(self) -> Graph:
        return self._generator.generate()


class RmatGenerator:
    def __init__(self, *, scale: int, edgeFactor: int, a: float, b: float, c: float, d: float) -> None:
        self._generator = _NetworKitRmatGenerator(scale, edgeFactor, a, b, c, d)

    def generate(self) -> Graph:
        return self._generator.generate()


class ClusteredRandomGraphGenerator:
    def __init__(self, *, n: int, k: int, pIntra: float, pInter: float) -> None:
        self._generator = _NetworKitClusteredRandomGraphGenerator(n, k, pIntra, pInter)

    def generate(self) -> Graph:
        return self._generator.generate()


class HyperbolicGenerator:
    def __init__(self, *, n: int, k: float = 6.0, gamma: float = 3.0, T: float = 0.0) -> None:
        self._generator = _NetworKitHyperbolicGenerator(n, k, gamma, T)

    def generate(self) -> Graph:
        return self._generator.generate()


class ChungLuGenerator:
    def __init__(self, *, degreeSequence: list[float]) -> None:
        self._generator = _NetworKitChungLuGenerator(degreeSequence)

    def generate(self) -> Graph:
        return self._generator.generate()


def generate_barabasi_albert(*, k: int, n_max: int, n0: int, batagelj: bool = True) -> GeneratedGraph:
    generator = BarabasiAlbertGenerator(k=k, nMax=n_max, n0=n0, batagelj=batagelj)
    return _generated_graph(generator.generate())


def generate_erdos_renyi_gnp(
    *,
    n: int,
    p: float,
    directed: bool = False,
    self_loops: bool = False,
) -> GeneratedGraph:
    generator = ErdosRenyiGenerator(nNodes=n, prob=p, directed=directed, selfLoops=self_loops)
    return _generated_graph(generator.generate())


def generate_watts_strogatz(*, n: int, n_neighbors: int, p: float) -> GeneratedGraph:
    generator = WattsStrogatzGenerator(nNodes=n, nNeighbors=n_neighbors, p=p)
    return _generated_graph(generator.generate())


def generate_configuration_model(
    *,
    sequence: list[int],
    variant: str,
    ignore_if_not_realizable: bool = False,
    num_switches_per_edge: int = 10,
) -> GeneratedGraph:
    if variant == "edge_switching":
        generator = EdgeSwitchingMarkovChainGenerator(
            degreeSequence=sequence,
            ignoreIfNotRealizable=ignore_if_not_realizable,
            numSwitchesPerEdge=num_switches_per_edge,
        )
        return _generated_graph(generator.generate())
    havel_hakimi = HavelHakimiGenerator(
        sequence=sorted(sequence, reverse=True), ignoreIfRealizable=ignore_if_not_realizable
    )
    return _generated_graph(havel_hakimi.generate())


def generate_rmat(*, scale: int, edge_factor: int, a: float, b: float, c: float, d: float) -> GeneratedGraph:
    generator = RmatGenerator(scale=scale, edgeFactor=edge_factor, a=a, b=b, c=c, d=d)
    return _generated_graph(generator.generate())


def generate_community_clustered(
    *,
    variant: str,
    n: int,
    k: int | None = None,
    p_intra: float | None = None,
    p_inter: float | None = None,
    average_degree: int | None = None,
    max_degree: int | None = None,
    tau1: float | None = None,
    min_community: int | None = None,
    max_community: int | None = None,
    tau2: float | None = None,
    mu: float | None = None,
) -> GeneratedGraph:
    if variant == "clustered_random":
        assert k is not None and p_intra is not None and p_inter is not None
        generator = ClusteredRandomGraphGenerator(n=n, k=k, pIntra=p_intra, pInter=p_inter)
        return _generated_graph(generator.generate())

    assert average_degree is not None and max_degree is not None
    assert tau1 is not None and tau2 is not None and mu is not None
    assert min_community is not None and max_community is not None
    generator = _NetworKitLFRGenerator(n)
    generator.generatePowerlawDegreeSequence(average_degree, max_degree, -tau1)
    generator.generatePowerlawCommunitySizeSequence(min_community, max_community, -tau2)
    generator.setMu(mu)
    generator.run()
    return _generated_graph(generator.getGraph())


def generate_hyperbolic(*, n: int, k: float = 6.0, gamma: float = 3.0, t: float = 0.0) -> GeneratedGraph:
    generator = HyperbolicGenerator(n=n, k=k, gamma=gamma, T=t)
    return _generated_graph(generator.generate())


def generate_chung_lu(*, degree_sequence: list[float]) -> GeneratedGraph:
    generator = ChungLuGenerator(degreeSequence=degree_sequence)
    return _generated_graph(generator.generate())


def _generated_graph(graph: Graph) -> GeneratedGraph:
    return GeneratedGraph(
        graph=graph,
        num_nodes=int(graph.numberOfNodes()),
        num_edges=int(graph.numberOfEdges()),
        directed=bool(graph.isDirected()),
    )
