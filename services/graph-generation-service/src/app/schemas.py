from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal, Self, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, model_validator


class RequestParameterError(ValueError):
    def __init__(self, parameter_name: str, reason: str) -> None:
        self.parameter_name = parameter_name
        super().__init__(reason)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


OutputFormat: TypeAlias = Literal["edge_list", "adjacency", "graphml", "gml", "graph6"]
LabelMode: TypeAlias = Literal["index", "uuid"]
Probability: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveFloat: TypeAlias = Annotated[float, Field(gt=0.0)]
NonNegativeFloat: TypeAlias = Annotated[float, Field(ge=0.0)]
MAX_GRAPH_NODES = 10_000


class OutputOptions(StrictBaseModel):
    format: OutputFormat = "edge_list"
    directed: bool = False
    labels: LabelMode = "index"

    @model_validator(mode="after")
    def validate_graph6_options(self) -> Self:
        if self.format == "graph6" and self.directed:
            raise ValueError("graph6 does not support directed graphs")
        if self.format == "graph6" and self.labels != "index":
            raise ValueError("graph6 does not support UUID labels")

        return self


class BackendDiscriminatedRequest(StrictBaseModel):
    DEFAULT_BACKEND: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def inject_backend_into_params(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        backend = data.get("backend", cls.DEFAULT_BACKEND)
        params = data.get("params")
        updated = {**data, "backend": backend}
        if isinstance(params, dict) and "backend" not in params:
            updated["params"] = {**params, "backend": backend}

        return updated

    @model_validator(mode="after")
    def validate_backend_consistency(self) -> Self:
        params = getattr(self, "params", None)
        backend = getattr(self, "backend", None)
        if params is not None and backend != params.backend:
            raise ValueError("backend must match params.backend")

        return self


class NetworkXBarabasiAlbertParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    m: PositiveInt
    seed: int | None = None


class IgraphBarabasiAlbertParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    m: PositiveInt
    power: float = 1.0
    zero_appeal: float = 1.0


class NetworKitBarabasiAlbertParams(StrictBaseModel):
    backend: Literal["networkit"]
    k: PositiveInt
    nMax: PositiveInt
    n0: PositiveInt
    batagelj: bool = True


BarabasiAlbertParams: TypeAlias = Annotated[
    NetworkXBarabasiAlbertParams | IgraphBarabasiAlbertParams | NetworKitBarabasiAlbertParams,
    Field(discriminator="backend"),
]


class BarabasiAlbertRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["barabasi_albert"]
    backend: Literal["networkx", "igraph", "networkit"] = "networkx"
    params: BarabasiAlbertParams
    output: OutputOptions = Field(default_factory=OutputOptions)


class ForestFireParams(StrictBaseModel):
    n: PositiveInt
    fw_prob: float
    bw_factor: float = 0.0
    ambs: PositiveInt = 1


class ForestFireRequest(StrictBaseModel):
    algorithm: Literal["forest_fire"]
    backend: Literal["igraph"] = "igraph"
    params: ForestFireParams
    output: OutputOptions = Field(default_factory=OutputOptions)


class NetworkXErdosRenyiGnpParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    p: Probability
    seed: int | None = None


class IgraphErdosRenyiGnpParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    p: Probability
    loops: bool = False


class NetworKitErdosRenyiGnpParams(StrictBaseModel):
    backend: Literal["networkit"]
    n: PositiveInt
    p: Probability
    selfLoops: bool = False


ErdosRenyiGnpParams: TypeAlias = Annotated[
    NetworkXErdosRenyiGnpParams | IgraphErdosRenyiGnpParams | NetworKitErdosRenyiGnpParams,
    Field(discriminator="backend"),
]


class ErdosRenyiGnpRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["erdos_renyi_gnp"]
    backend: Literal["networkx", "igraph", "networkit"] = "networkx"
    params: ErdosRenyiGnpParams
    output: OutputOptions = Field(default_factory=OutputOptions)


class NetworkXErdosRenyiGnmParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    m: NonNegativeInt
    seed: int | None = None


class IgraphErdosRenyiGnmParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    m: NonNegativeInt


ErdosRenyiGnmParams: TypeAlias = Annotated[
    NetworkXErdosRenyiGnmParams | IgraphErdosRenyiGnmParams,
    Field(discriminator="backend"),
]


class ErdosRenyiGnmRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["erdos_renyi_gnm"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: ErdosRenyiGnmParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_edge_count(self) -> Self:
        n = self.params.n
        max_edges = n * (n - 1) if self.output.directed else n * (n - 1) // 2
        if self.params.m > max_edges:
            raise RequestParameterError("params.m", f"m must not exceed {max_edges} for the requested graph")

        return self


class NetworkXWattsStrogatzParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    k: PositiveInt
    p: Probability
    seed: int | None = None
    variant: Literal["standard", "connected"] = "standard"
    tries: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_variant_options(self) -> Self:
        if self.k > self.n:
            raise RequestParameterError("params.k", "k must not exceed n")
        if self.variant == "standard" and self.tries is not None:
            raise RequestParameterError("params.tries", "tries is only supported by the connected variant")
        if self.variant == "connected" and self.n > 1 and self.k < 2:
            raise RequestParameterError("params.k", "k must be at least 2 for the connected variant")

        return self


class IgraphWattsStrogatzParams(StrictBaseModel):
    backend: Literal["igraph"]
    dim: PositiveInt
    size: PositiveInt
    nei: PositiveInt
    p: Probability


class NetworKitWattsStrogatzParams(StrictBaseModel):
    backend: Literal["networkit"]
    n: PositiveInt
    nNeighbors: PositiveInt
    p: Probability

    @model_validator(mode="after")
    def validate_neighbor_count(self) -> Self:
        if 2 * self.nNeighbors >= self.n - 1:
            raise RequestParameterError(
                "params.nNeighbors",
                "2 * nNeighbors must be less than n - 1",
            )

        return self


WattsStrogatzParams: TypeAlias = Annotated[
    NetworkXWattsStrogatzParams | IgraphWattsStrogatzParams | NetworKitWattsStrogatzParams,
    Field(discriminator="backend"),
]


class WattsStrogatzRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["watts_strogatz"]
    backend: Literal["networkx", "igraph", "networkit"] = "networkx"
    params: WattsStrogatzParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "Watts-Strogatz generators produce undirected graphs")

        return self


class NetworkXConfigurationModelParams(StrictBaseModel):
    backend: Literal["networkx"]
    sequence: list[NonNegativeInt]
    variant: Literal["configuration", "havel_hakimi", "expected_degree"] = "configuration"
    seed: int | None = None
    selfloops: bool = True

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if not self.sequence:
            raise RequestParameterError("params.sequence", "sequence must not be empty")
        if self.variant != "expected_degree" and sum(self.sequence) % 2:
            raise RequestParameterError("params.sequence", "degree sum must be even")
        return self


class IgraphConfigurationModelParams(StrictBaseModel):
    backend: Literal["igraph"]
    out: list[NonNegativeInt]
    in_: list[NonNegativeInt] | None = Field(default=None, alias="in")
    method: Literal[
        "configuration",
        "fast_heur_simple",
        "configuration_simple",
        "edge_switching_simple",
        "vl",
    ] = "configuration"

    @model_validator(mode="after")
    def validate_sequences(self) -> Self:
        if not self.out:
            raise RequestParameterError("params.out", "out must not be empty")
        if self.in_ is None and sum(self.out) % 2:
            raise RequestParameterError("params.out", "degree sum must be even")
        if self.in_ is not None:
            if len(self.in_) != len(self.out):
                raise RequestParameterError("params.in", "in and out must have the same length")
            if sum(self.in_) != sum(self.out):
                raise RequestParameterError("params.in", "in-degree and out-degree sums must match")
        return self


class NetworKitConfigurationModelParams(StrictBaseModel):
    backend: Literal["networkit"]
    sequence: list[NonNegativeInt]
    variant: Literal["havel_hakimi", "edge_switching"] = "havel_hakimi"
    ignoreIfNotRealizable: bool = False
    numSwitchesPerEdge: PositiveInt = 10

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if not self.sequence:
            raise RequestParameterError("params.sequence", "sequence must not be empty")
        if sum(self.sequence) % 2:
            raise RequestParameterError("params.sequence", "degree sum must be even")
        if any(degree >= len(self.sequence) for degree in self.sequence):
            raise RequestParameterError("params.sequence", "every degree must be smaller than the sequence length")
        return self


ConfigurationModelParams: TypeAlias = Annotated[
    NetworkXConfigurationModelParams | IgraphConfigurationModelParams | NetworKitConfigurationModelParams,
    Field(discriminator="backend"),
]


class ConfigurationModelRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["configuration_model"]
    backend: Literal["networkx", "igraph", "networkit"] = "networkx"
    params: ConfigurationModelParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        directed = isinstance(self.params, IgraphConfigurationModelParams) and self.params.in_ is not None
        if self.output.directed != directed:
            reason = (
                "directed output requires an igraph in-degree sequence"
                if self.output.directed
                else "in requires directed output"
            )
            raise RequestParameterError("output.directed", reason)
        return self


class NetworkXStochasticBlockModelParams(StrictBaseModel):
    backend: Literal["networkx"]
    sizes: list[PositiveInt]
    p: list[list[Probability]]
    selfloops: bool = False
    seed: int | None = None

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        if len(self.p) != len(self.sizes) or any(len(row) != len(self.sizes) for row in self.p):
            raise RequestParameterError("params.p", "p must be a square matrix matching sizes")
        return self


class IgraphStochasticBlockModelParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    pref_matrix: list[list[Probability]]
    block_sizes: list[PositiveInt]

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        blocks = len(self.block_sizes)
        if sum(self.block_sizes) != self.n:
            raise RequestParameterError("params.block_sizes", "block_sizes must sum to n")
        if len(self.pref_matrix) != blocks or any(len(row) != blocks for row in self.pref_matrix):
            raise RequestParameterError("params.pref_matrix", "pref_matrix must be square and match block_sizes")
        return self


StochasticBlockModelParams: TypeAlias = Annotated[
    NetworkXStochasticBlockModelParams | IgraphStochasticBlockModelParams,
    Field(discriminator="backend"),
]


class StochasticBlockModelRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["stochastic_block_model"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: StochasticBlockModelParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_matrix_symmetry(self) -> Self:
        matrix = (
            self.params.p if isinstance(self.params, NetworkXStochasticBlockModelParams) else self.params.pref_matrix
        )
        if not self.output.directed and any(matrix[i][j] != matrix[j][i] for i in range(len(matrix)) for j in range(i)):
            raise RequestParameterError("params", "probability matrix must be symmetric for an undirected graph")
        return self


class NetworkXRandomRegularParams(StrictBaseModel):
    backend: Literal["networkx"]
    d: PositiveInt
    n: PositiveInt
    seed: int | None = None

    @model_validator(mode="after")
    def validate_degree(self) -> Self:
        if self.d >= self.n:
            raise RequestParameterError("params.d", "d must be smaller than n")
        if self.d * self.n % 2:
            raise RequestParameterError("params.d", "d * n must be even")
        return self


class IgraphRandomRegularParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    k: PositiveInt
    multiple: bool = False

    @model_validator(mode="after")
    def validate_degree(self) -> Self:
        if not self.multiple and self.k >= self.n:
            raise RequestParameterError("params.k", "k must be smaller than n for a simple graph")
        return self


RandomRegularParams: TypeAlias = Annotated[
    NetworkXRandomRegularParams | IgraphRandomRegularParams,
    Field(discriminator="backend"),
]


class RandomRegularRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["random_regular"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: RandomRegularParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed and isinstance(self.params, NetworkXRandomRegularParams):
            raise RequestParameterError("output.directed", "NetworkX random regular graphs are undirected")
        if (
            not self.output.directed
            and isinstance(self.params, IgraphRandomRegularParams)
            and self.params.k * self.params.n % 2
        ):
            raise RequestParameterError("params.k", "k * n must be even for an undirected graph")
        return self


class NetworkXRandomGeometricParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    radius: PositiveFloat
    dim: PositiveInt = 2
    p: PositiveFloat = 2.0
    seed: int | None = None
    variant: Literal["random_geometric", "soft_random_geometric"] = "random_geometric"


class IgraphRandomGeometricParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    radius: PositiveFloat
    torus: bool = False


RandomGeometricParams: TypeAlias = Annotated[
    NetworkXRandomGeometricParams | IgraphRandomGeometricParams,
    Field(discriminator="backend"),
]


class RandomGeometricRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["random_geometric"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: RandomGeometricParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "random geometric generators produce undirected graphs")
        return self


class NetworKitKroneckerRmatParams(StrictBaseModel):
    scale: PositiveInt
    edgeFactor: PositiveInt
    a: Probability
    b: Probability
    c: Probability
    d: Probability

    @model_validator(mode="after")
    def validate_probabilities(self) -> Self:
        if abs(self.a + self.b + self.c + self.d - 1.0) > 1e-9:
            raise RequestParameterError("params", "a, b, c, and d must sum to 1")
        return self


class KroneckerRmatRequest(StrictBaseModel):
    algorithm: Literal["kronecker_rmat"]
    backend: Literal["networkit"] = "networkit"
    params: NetworKitKroneckerRmatParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "NetworKit R-MAT graphs are undirected")
        return self


class ClassicDeterministicParams(StrictBaseModel):
    shape: Literal["complete", "star", "wheel", "path", "cycle", "grid", "hypercube", "lattice"]
    n: PositiveInt | None = None
    rows: PositiveInt | None = None
    cols: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        if self.shape in {"grid", "lattice"}:
            if self.rows is None or self.cols is None:
                raise RequestParameterError("params.rows", "rows and cols are required for grid and lattice shapes")
            if self.n is not None:
                raise RequestParameterError("params.n", "n is not used for grid and lattice shapes")
        elif self.n is None:
            raise RequestParameterError("params.n", "n is required for this shape")
        elif self.rows is not None or self.cols is not None:
            raise RequestParameterError("params.rows", "rows and cols are only used for grid and lattice shapes")
        if self.shape == "wheel" and self.n is not None and self.n < 4:
            raise RequestParameterError("params.n", "wheel graphs require at least 4 nodes")
        return self


class NetworkXClassicDeterministicParams(ClassicDeterministicParams):
    backend: Literal["networkx"]


class IgraphClassicDeterministicParams(ClassicDeterministicParams):
    backend: Literal["igraph"]


ClassicDeterministicBackendParams: TypeAlias = Annotated[
    NetworkXClassicDeterministicParams | IgraphClassicDeterministicParams,
    Field(discriminator="backend"),
]


class ClassicDeterministicRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["classic_deterministic"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: ClassicDeterministicBackendParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "classic deterministic generators produce undirected graphs")
        return self


class NamedGraphParams(StrictBaseModel):
    name: Literal["petersen", "chvatal", "tutte", "karate_club"]


class NetworkXNamedGraphParams(NamedGraphParams):
    backend: Literal["networkx"]


class IgraphNamedGraphParams(NamedGraphParams):
    backend: Literal["igraph"]


NamedGraphBackendParams: TypeAlias = Annotated[
    NetworkXNamedGraphParams | IgraphNamedGraphParams,
    Field(discriminator="backend"),
]


class NamedGraphRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["named_graph"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: NamedGraphBackendParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "named graphs are undirected")
        return self


class NetworkXRandomTreeParams(StrictBaseModel):
    backend: Literal["networkx"]
    n: PositiveInt
    variant: Literal["random_labeled", "random_powerlaw"] = "random_labeled"
    gamma: float | None = None
    seed: int | None = None
    tries: PositiveInt = 100

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        if self.variant == "random_powerlaw" and self.gamma is not None and self.gamma <= 0:
            raise RequestParameterError("params.gamma", "gamma must be greater than 0")
        if self.variant != "random_powerlaw" and self.gamma is not None:
            raise RequestParameterError("params.gamma", "gamma is only used by random_powerlaw")
        return self


class IgraphRandomTreeParams(StrictBaseModel):
    backend: Literal["igraph"]
    n: PositiveInt
    variant: Literal["tree_game"] = "tree_game"
    method: Literal["lerw", "prufer", "random"] = "lerw"


RandomTreeParams: TypeAlias = Annotated[
    NetworkXRandomTreeParams | IgraphRandomTreeParams,
    Field(discriminator="backend"),
]


class RandomTreeRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["random_tree"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: RandomTreeParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        if isinstance(self.params, IgraphRandomTreeParams) and self.output.directed and self.params.method == "prufer":
            raise RequestParameterError("params.method", "the prufer method does not support directed trees")
        return self


class RandomBipartiteParams(StrictBaseModel):
    n1: PositiveInt
    n2: PositiveInt
    p: Probability | None = None
    m: NonNegativeInt | None = None

    @model_validator(mode="after")
    def validate_density(self) -> Self:
        if (self.p is None) == (self.m is None):
            raise RequestParameterError("params", "exactly one of p or m is required")
        if self.m is not None and self.m > self.n1 * self.n2:
            raise RequestParameterError("params.m", "m must not exceed n1 * n2")
        return self


class NetworkXRandomBipartiteParams(RandomBipartiteParams):
    backend: Literal["networkx"]
    seed: int | None = None


class IgraphRandomBipartiteParams(RandomBipartiteParams):
    backend: Literal["igraph"]


RandomBipartiteBackendParams: TypeAlias = Annotated[
    NetworkXRandomBipartiteParams | IgraphRandomBipartiteParams,
    Field(discriminator="backend"),
]


class RandomBipartiteRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["random_bipartite"]
    backend: Literal["networkx", "igraph"] = "networkx"
    params: RandomBipartiteBackendParams
    output: OutputOptions = Field(default_factory=OutputOptions)


class NetworkXCommunityClusteredParams(StrictBaseModel):
    backend: Literal["networkx"]
    variant: Literal["planted_partition", "gaussian_random_partition", "lfr", "relaxed_caveman"]
    n: PositiveInt | None = None
    l: PositiveInt | None = None  # noqa: E741 - matches the NetworkX API
    k: PositiveInt | None = None
    s: PositiveFloat | None = None
    v: NonNegativeFloat | None = None
    p: Probability | None = None
    pIntra: Probability | None = None
    pInter: Probability | None = None
    tau1: PositiveFloat | None = None
    tau2: PositiveFloat | None = None
    mu: Probability | None = None
    averageDegree: PositiveInt | None = None
    minDegree: PositiveInt | None = None
    maxDegree: PositiveInt | None = None
    minCommunity: PositiveInt | None = None
    maxCommunity: PositiveInt | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        required: dict[str, tuple[str, ...]] = {
            "planted_partition": ("l", "k", "pIntra", "pInter"),
            "gaussian_random_partition": ("n", "s", "v", "pIntra", "pInter"),
            "lfr": ("n", "tau1", "tau2", "mu"),
            "relaxed_caveman": ("l", "k", "p"),
        }
        missing = [name for name in required[self.variant] if getattr(self, name) is None]
        if missing:
            raise RequestParameterError(f"params.{missing[0]}", f"{missing[0]} is required for {self.variant}")
        if self.variant == "lfr" and self.averageDegree is None and self.minDegree is None:
            raise RequestParameterError("params.averageDegree", "averageDegree or minDegree is required for lfr")
        return self


class NetworKitCommunityClusteredParams(StrictBaseModel):
    backend: Literal["networkit"]
    variant: Literal["clustered_random", "lfr"]
    n: PositiveInt
    k: PositiveInt | None = None
    pIntra: Probability | None = None
    pInter: Probability | None = None
    tau1: PositiveFloat | None = None
    tau2: PositiveFloat | None = None
    mu: Probability | None = None
    averageDegree: PositiveInt | None = None
    maxDegree: PositiveInt | None = None
    minCommunity: PositiveInt | None = None
    maxCommunity: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        required = (
            ("k", "pIntra", "pInter")
            if self.variant == "clustered_random"
            else ("tau1", "tau2", "mu", "averageDegree", "maxDegree", "minCommunity", "maxCommunity")
        )
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise RequestParameterError(f"params.{missing[0]}", f"{missing[0]} is required for {self.variant}")
        return self


CommunityClusteredParams: TypeAlias = Annotated[
    NetworkXCommunityClusteredParams | NetworKitCommunityClusteredParams,
    Field(discriminator="backend"),
]


class CommunityClusteredRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["community_clustered"]
    backend: Literal["networkx", "networkit"] = "networkx"
    params: CommunityClusteredParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed and self.params.variant in {"relaxed_caveman", "clustered_random", "lfr"}:
            raise RequestParameterError("output.directed", f"{self.params.variant} produces an undirected graph")
        return self


class HyperbolicParams(StrictBaseModel):
    n: PositiveInt
    k: PositiveFloat = 6.0
    gamma: Annotated[float, Field(gt=2.0)] = 3.0
    T: NonNegativeFloat = 0.0


class HyperbolicRequest(StrictBaseModel):
    algorithm: Literal["hyperbolic"]
    backend: Literal["networkit"] = "networkit"
    params: HyperbolicParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "hyperbolic generators produce undirected graphs")
        return self


class ChungLuParams(StrictBaseModel):
    degreeSequence: list[NonNegativeFloat]

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if not self.degreeSequence:
            raise RequestParameterError("params.degreeSequence", "degreeSequence must not be empty")
        return self


class NetworkXChungLuParams(ChungLuParams):
    backend: Literal["networkx"]
    selfloops: bool = True
    seed: int | None = None


class NetworKitChungLuParams(ChungLuParams):
    backend: Literal["networkit"]


ChungLuBackendParams: TypeAlias = Annotated[
    NetworkXChungLuParams | NetworKitChungLuParams,
    Field(discriminator="backend"),
]


class ChungLuRequest(BackendDiscriminatedRequest):
    DEFAULT_BACKEND: ClassVar[str] = "networkx"

    algorithm: Literal["chung_lu"]
    backend: Literal["networkx", "networkit"] = "networkx"
    params: ChungLuBackendParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "Chung-Lu generators produce undirected graphs")
        return self


class StaticFitnessParams(StrictBaseModel):
    variant: Literal["static_fitness", "static_power_law"] = "static_fitness"
    m: PositiveInt
    fitness_out: list[PositiveFloat] | None = None
    fitness_in: list[PositiveFloat] | None = None
    n: PositiveInt | None = None
    exponent_out: float | None = None
    exponent_in: float | None = None

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        if self.variant == "static_fitness":
            if not self.fitness_out:
                raise RequestParameterError("params.fitness_out", "fitness_out is required for static_fitness")
        elif self.n is None or self.exponent_out is None:
            name = "n" if self.n is None else "exponent_out"
            raise RequestParameterError(f"params.{name}", f"{name} is required for static_power_law")
        return self


class StaticFitnessRequest(StrictBaseModel):
    algorithm: Literal["static_fitness"]
    backend: Literal["igraph"] = "igraph"
    params: StaticFitnessParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        directed = (
            self.params.fitness_in is not None
            if self.params.variant == "static_fitness"
            else (self.params.exponent_in is not None and self.params.exponent_in != -1)
        )
        if self.output.directed != directed:
            raise RequestParameterError(
                "output.directed", "directed output must match the presence of inbound fitness parameters"
            )
        return self


class GrowingAttachmentParams(StrictBaseModel):
    variant: Literal["growing_random", "establishment", "preference", "asymmetric_preference", "recent_degree"]
    n: PositiveInt
    m: PositiveInt | None = None
    power: float | None = None
    k: PositiveInt | None = None
    type_dist: list[Probability] | None = None
    type_dist_matrix: list[list[Probability]] | None = None
    pref_matrix: list[list[Probability]] | None = None
    window: PositiveInt | None = None
    citation: bool = False
    outpref: bool = False
    loops: bool = False

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        required: dict[str, tuple[str, ...]] = {
            "growing_random": ("m",),
            "establishment": ("k", "type_dist", "pref_matrix"),
            "preference": ("type_dist", "pref_matrix"),
            "asymmetric_preference": ("type_dist_matrix", "pref_matrix"),
            "recent_degree": ("m", "window"),
        }
        missing = [name for name in required[self.variant] if getattr(self, name) is None]
        if missing:
            raise RequestParameterError(f"params.{missing[0]}", f"{missing[0]} is required for {self.variant}")
        if self.power is not None and self.variant != "recent_degree":
            raise RequestParameterError("params.power", "power is only used by recent_degree")
        if (
            self.variant in {"establishment", "preference"}
            and self.type_dist is not None
            and self.pref_matrix is not None
        ):
            if len(self.pref_matrix) != len(self.type_dist) or any(
                len(row) != len(self.type_dist) for row in self.pref_matrix
            ):
                raise RequestParameterError("params.pref_matrix", "pref_matrix must be square and match type_dist")
        if (
            self.variant == "asymmetric_preference"
            and self.type_dist_matrix is not None
            and self.pref_matrix is not None
        ):
            if len(self.pref_matrix) != len(self.type_dist_matrix) or any(
                len(pref_row) != len(type_row)
                for pref_row, type_row in zip(self.pref_matrix, self.type_dist_matrix, strict=True)
            ):
                raise RequestParameterError("params.pref_matrix", "pref_matrix must match type_dist_matrix")
        return self


class GrowingAttachmentRequest(StrictBaseModel):
    algorithm: Literal["growing_attachment"]
    backend: Literal["igraph"] = "igraph"
    params: GrowingAttachmentParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.params.variant == "asymmetric_preference" and not self.output.directed:
            raise RequestParameterError("output.directed", "asymmetric_preference produces a directed graph")
        return self


class KleinbergSmallWorldParams(StrictBaseModel):
    n: PositiveInt
    p: PositiveInt = 1
    q: PositiveInt = 1
    r: PositiveInt = 2
    dim: PositiveInt = 2
    seed: int | None = None


class KleinbergSmallWorldRequest(StrictBaseModel):
    algorithm: Literal["kleinberg_small_world"]
    backend: Literal["networkx"] = "networkx"
    params: KleinbergSmallWorldParams
    output: OutputOptions = Field(default_factory=lambda: OutputOptions(directed=True))

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if not self.output.directed:
            raise RequestParameterError("output.directed", "Kleinberg small-world graphs are directed")
        return self


class PowerlawClusterParams(StrictBaseModel):
    n: PositiveInt
    m: PositiveInt
    p: Probability
    seed: int | None = None

    @model_validator(mode="after")
    def validate_attachment_count(self) -> Self:
        if self.m >= self.n:
            raise RequestParameterError("params.m", "m must be smaller than n")
        return self


class PowerlawClusterRequest(StrictBaseModel):
    algorithm: Literal["powerlaw_cluster"]
    backend: Literal["networkx"] = "networkx"
    params: PowerlawClusterParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "power-law cluster graphs are undirected")
        return self


class GeometricThresholdParams(StrictBaseModel):
    variant: Literal["waxman", "geographical_threshold"] = "waxman"
    n: PositiveInt
    beta: Probability | None = None
    alpha: PositiveFloat | None = None
    theta: PositiveFloat | None = None
    dim: PositiveInt = 2
    seed: int | None = None

    @model_validator(mode="after")
    def validate_variant(self) -> Self:
        if self.variant == "waxman" and (self.beta is None or self.alpha is None):
            name = "beta" if self.beta is None else "alpha"
            raise RequestParameterError(f"params.{name}", f"{name} is required for waxman")
        if self.variant == "geographical_threshold" and self.theta is None:
            raise RequestParameterError("params.theta", "theta is required for geographical_threshold")
        return self


class GeometricThresholdRequest(StrictBaseModel):
    algorithm: Literal["geometric_threshold"]
    backend: Literal["networkx"] = "networkx"
    params: GeometricThresholdParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "geometric threshold generators produce undirected graphs")
        return self


class DuplicationDivergenceParams(StrictBaseModel):
    n: PositiveInt
    seed: int | None = None


class DuplicationDivergenceRequest(StrictBaseModel):
    algorithm: Literal["duplication_divergence"]
    backend: Literal["networkx"] = "networkx"
    params: DuplicationDivergenceParams
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def validate_directedness(self) -> Self:
        if self.output.directed:
            raise RequestParameterError("output.directed", "internet-AS graphs are undirected")
        return self


GraphGenerationRequestValue: TypeAlias = (
    ErdosRenyiGnpRequest
    | ErdosRenyiGnmRequest
    | WattsStrogatzRequest
    | BarabasiAlbertRequest
    | ConfigurationModelRequest
    | StochasticBlockModelRequest
    | RandomRegularRequest
    | RandomGeometricRequest
    | ForestFireRequest
    | KroneckerRmatRequest
    | ClassicDeterministicRequest
    | NamedGraphRequest
    | RandomTreeRequest
    | RandomBipartiteRequest
    | CommunityClusteredRequest
    | HyperbolicRequest
    | ChungLuRequest
    | StaticFitnessRequest
    | GrowingAttachmentRequest
    | KleinbergSmallWorldRequest
    | PowerlawClusterRequest
    | GeometricThresholdRequest
    | DuplicationDivergenceRequest
)


def _bounded_power(base: int, exponent: int) -> int:
    if base > 1 and exponent > MAX_GRAPH_NODES.bit_length():
        return MAX_GRAPH_NODES + 1
    return int(base**exponent)


def validate_graph_size(request: GraphGenerationRequestValue) -> None:
    params = request.params.model_dump(by_alias=True)
    algorithm = request.algorithm
    if algorithm == "kronecker_rmat":
        node_count = _bounded_power(2, params["scale"])
    elif algorithm in {"watts_strogatz", "kleinberg_small_world"} and "dim" in params:
        base = params["size"] if "size" in params else params["n"]
        node_count = _bounded_power(base, params["dim"])
    elif algorithm == "classic_deterministic" and params.get("shape") in {"grid", "lattice"}:
        node_count = params["rows"] * params["cols"]
    elif algorithm == "classic_deterministic" and params.get("shape") == "hypercube":
        node_count = _bounded_power(2, params["n"])
    elif algorithm == "random_bipartite":
        node_count = params["n1"] + params["n2"]
    elif algorithm == "community_clustered" and params.get("n") is None:
        node_count = params["l"] * params["k"]
    elif isinstance(params.get("n"), int):
        node_count = params["n"]
    elif isinstance(params.get("nMax"), int):
        node_count = params["nMax"]
    elif isinstance(params.get("sizes"), list):
        node_count = sum(params["sizes"])
    else:
        sequence = next(
            (params[name] for name in ("sequence", "out", "degreeSequence", "fitness_out") if params.get(name)),
            (),
        )
        node_count = len(sequence)

    if node_count > MAX_GRAPH_NODES:
        raise RequestParameterError("params", f"graph must not exceed {MAX_GRAPH_NODES} nodes")


GraphGenerationRequest: TypeAlias = Annotated[
    GraphGenerationRequestValue,
    Field(discriminator="algorithm"),
]


class GraphMetadata(StrictBaseModel):
    numNodes: int | None = None
    numEdges: int | None = None
    directed: bool
    createdAt: str
    generationTimeMs: int


class GraphLinks(StrictBaseModel):
    self: str
    export: str


class GraphResource(StrictBaseModel):
    id: str
    status: Literal["pending", "completed", "failed"]
    algorithm: str
    backend: str
    params: dict[str, Any]
    metadata: GraphMetadata
    links: GraphLinks = Field(alias="_links")


class AlgorithmBackendDescriptor(StrictBaseModel):
    algorithm: str
    backend: str
    canonicalFamily: str
    paramsSchema: str
    defaultBackend: bool = False


class AlgorithmCatalogResponse(StrictBaseModel):
    algorithms: list[AlgorithmBackendDescriptor]
    schemas: dict[str, Any]


class InvalidParam(StrictBaseModel):
    name: str
    reason: str


class ProblemDetails(StrictBaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    invalidParams: list[InvalidParam]
