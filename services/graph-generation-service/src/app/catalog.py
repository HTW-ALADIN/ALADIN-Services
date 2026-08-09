from __future__ import annotations

from app.schemas import AlgorithmBackendDescriptor

CatalogRow = tuple[str, str, str, str, bool]
AlgorithmSchema = tuple[str, tuple[tuple[str, str], ...]]

CATALOG_ROWS: tuple[CatalogRow, ...] = (
    ("erdos_renyi_gnp", "networkx", "Erdos-Renyi G(n,p)", "NetworkXErdosRenyiGnpParams", True),
    ("erdos_renyi_gnp", "igraph", "Erdos-Renyi G(n,p)", "IgraphErdosRenyiGnpParams", False),
    ("erdos_renyi_gnp", "networkit", "Erdos-Renyi G(n,p)", "NetworKitErdosRenyiGnpParams", False),
    ("erdos_renyi_gnm", "networkx", "Erdos-Renyi G(n,m)", "NetworkXErdosRenyiGnmParams", True),
    ("erdos_renyi_gnm", "igraph", "Erdos-Renyi G(n,m)", "IgraphErdosRenyiGnmParams", False),
    ("watts_strogatz", "networkx", "Watts-Strogatz small-world", "NetworkXWattsStrogatzParams", True),
    ("watts_strogatz", "igraph", "Watts-Strogatz small-world", "IgraphWattsStrogatzParams", False),
    ("watts_strogatz", "networkit", "Watts-Strogatz small-world", "NetworKitWattsStrogatzParams", False),
    ("barabasi_albert", "networkx", "Barabasi-Albert preferential attachment", "NetworkXBarabasiAlbertParams", True),
    ("barabasi_albert", "igraph", "Barabasi-Albert preferential attachment", "IgraphBarabasiAlbertParams", False),
    ("barabasi_albert", "networkit", "Barabasi-Albert preferential attachment", "NetworKitBarabasiAlbertParams", False),
    (
        "configuration_model",
        "networkx",
        "Degree-sequence / configuration model",
        "NetworkXConfigurationModelParams",
        True,
    ),
    ("configuration_model", "igraph", "Degree-sequence / configuration model", "IgraphConfigurationModelParams", False),
    (
        "configuration_model",
        "networkit",
        "Degree-sequence / configuration model",
        "NetworKitConfigurationModelParams",
        False,
    ),
    ("stochastic_block_model", "networkx", "Stochastic block model", "NetworkXStochasticBlockModelParams", True),
    ("stochastic_block_model", "igraph", "Stochastic block model", "IgraphStochasticBlockModelParams", False),
    ("random_regular", "networkx", "Random k-regular graph", "NetworkXRandomRegularParams", True),
    ("random_regular", "igraph", "Random k-regular graph", "IgraphRandomRegularParams", False),
    ("random_geometric", "networkx", "Random geometric graph", "NetworkXRandomGeometricParams", True),
    ("random_geometric", "igraph", "Random geometric graph", "IgraphRandomGeometricParams", False),
    ("forest_fire", "igraph", "Forest-fire growth model", "ForestFireParams", True),
    ("kronecker_rmat", "networkit", "Kronecker / R-MAT", "NetworKitKroneckerRmatParams", True),
    (
        "classic_deterministic",
        "networkx",
        "Classic deterministic graphs",
        "NetworkXClassicDeterministicParams",
        True,
    ),
    (
        "classic_deterministic",
        "igraph",
        "Classic deterministic graphs",
        "IgraphClassicDeterministicParams",
        False,
    ),
    ("named_graph", "networkx", "Named / famous graphs", "NetworkXNamedGraphParams", True),
    ("named_graph", "igraph", "Named / famous graphs", "IgraphNamedGraphParams", False),
    ("random_tree", "networkx", "Random tree generators", "NetworkXRandomTreeParams", True),
    ("random_tree", "igraph", "Random tree generators", "IgraphRandomTreeParams", False),
    ("random_bipartite", "networkx", "Random bipartite graph", "NetworkXRandomBipartiteParams", True),
    ("random_bipartite", "igraph", "Random bipartite graph", "IgraphRandomBipartiteParams", False),
    (
        "community_clustered",
        "networkx",
        "Community / clustered models",
        "NetworkXCommunityClusteredParams",
        True,
    ),
    (
        "community_clustered",
        "networkit",
        "Community / clustered models",
        "NetworKitCommunityClusteredParams",
        False,
    ),
    ("hyperbolic", "networkit", "Hyperbolic random graph", "HyperbolicParams", True),
    ("chung_lu", "networkx", "Chung-Lu / expected-degree graph", "NetworkXChungLuParams", True),
    ("chung_lu", "networkit", "Chung-Lu / expected-degree graph", "NetworKitChungLuParams", False),
    ("static_fitness", "igraph", "Static fitness / power-law fitness model", "StaticFitnessParams", True),
    ("growing_attachment", "igraph", "Growing / establishment / preference models", "GrowingAttachmentParams", True),
    ("kleinberg_small_world", "networkx", "Kleinberg navigable small-world", "KleinbergSmallWorldParams", True),
    ("powerlaw_cluster", "networkx", "Holme-Kim power-law cluster model", "PowerlawClusterParams", True),
    ("geometric_threshold", "networkx", "Waxman / geographic-threshold graph", "GeometricThresholdParams", True),
    (
        "duplication_divergence",
        "networkx",
        "Duplication-divergence / internet-AS model",
        "DuplicationDivergenceParams",
        True,
    ),
)


ALGORITHM_CATALOG = [
    AlgorithmBackendDescriptor(
        algorithm=algorithm,
        backend=backend,
        canonicalFamily=canonical_family,
        paramsSchema=f"#/components/schemas/{params_schema}",
        defaultBackend=is_default,
    )
    for algorithm, backend, canonical_family, params_schema, is_default in CATALOG_ROWS
]


def _request_schema_name(algorithm: str) -> str:
    return "".join(part.title() for part in algorithm.split("_")) + "Request"


def _algorithm_schemas() -> dict[str, AlgorithmSchema]:
    variants_by_algorithm: dict[str, list[tuple[str, str]]] = {}
    for algorithm, backend, _canonical_family, params_schema, _is_default in CATALOG_ROWS:
        variants_by_algorithm.setdefault(algorithm, []).append((backend, params_schema))

    return {
        algorithm: (_request_schema_name(algorithm), tuple(variants))
        for algorithm, variants in variants_by_algorithm.items()
    }


ALGORITHM_SCHEMAS = _algorithm_schemas()
