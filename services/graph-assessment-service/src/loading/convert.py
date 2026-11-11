'''
Conversion between the JSON data format and networkx graphs.

The data format describes a graph with graph attributes, nodes and edges;
nodes and edges can carry attributes of their own. While loading, this
module checks the conditions that only show across several entries: unique
node IDs and endpoints that point to existing nodes.

The error texts end up in the feedback (the rejection reason) and stay German.
'''

import networkx as nx

from .checks import (
    GraphInputError,
    reject_dupe_edge,
    reject_dupe_node,
    require_dict,
    require_known_endpoint,
    require_str_id,
)

#: The networkx classes a notation may choose from. The same list is a
#: literal on Notation.graph_class (-> src/notation/notation.py): whoever adds
#: one here adds it there too.
GRAPH_CLASSES = {
    "Graph": nx.Graph,
    "DiGraph": nx.DiGraph,
    "MultiGraph": nx.MultiGraph,
    "MultiDiGraph": nx.MultiDiGraph,
}


def make_graph(notation):
    '''An empty networkx graph of the class the schema prescribes.'''
    graph_class = notation.graph_class

    if graph_class not in GRAPH_CLASSES:
        raise GraphInputError(
            f"Unbekannte graph_class: {graph_class!r} "
            f"(bekannt: {sorted(GRAPH_CLASSES)})"
        )

    return GRAPH_CLASSES[graph_class]()


def nx_from_dict(data, notation):
    '''
    Builds a networkx graph from the loaded data.

    Checked along the way: unique node IDs and existing nodes at both edge
    ends.
    '''
    require_dict(data, "Eingabe")

    # Take over the graph attributes and create the matching graph type.
    g = make_graph(notation)
    g.graph.update(require_dict(data.get("graph", {}), "'graph'"))
    # The schema id is stored as a graph attribute.
    g.graph["schema"] = data.get("schema")

    for i, node in enumerate(_list_at(data, "nodes")):
        where = f"nodes[{i}]"
        require_dict(node, where)
        node_id = require_str_id(node, where)
        reject_dupe_node(g, node_id, where)

        g.add_node(node_id, **{k: v for k, v in node.items() if k != "id"})

    for i, edge in enumerate(_list_at(data, "edges")):
        where = f"edges[{i}]"
        require_dict(edge, where)
        u, v = _endpoint_ids(edge, where)

        require_known_endpoint(g, u, f"{where}.endpoints[0]")
        require_known_endpoint(g, v, f"{where}.endpoints[1]")
        reject_dupe_edge(g, u, v, where)

        # Only a multi class can hold several edges between the same nodes --
        # otherwise reject_dupe_edge above has already rejected.
        g.add_edge(u, v, **require_dict(edge.get("properties", {}), f"{where}.properties"))

    return g


def dict_from_nx(g):
    '''
    Writes a networkx graph back into the JSON data format.

    Not a pipeline step: a run only goes one way, file -> graph. The way back
    shows that nothing is lost while loading -- the graph is written back,
    checked against the exchange format and loaded again; the result is the
    same graph.

    The order of nodes and edges does not have to match the input file, and
    for an undirected graph neither does the order of the two endpoints.
    '''
    graph_attrs = dict(g.graph)

    return {
        "schema": graph_attrs.pop("schema", None),
        "graph": graph_attrs,
        "nodes": [{"id": n, **attrs} for n, attrs in g.nodes(data=True)],
        "edges": [_edge_dict(u, v, attrs) for u, v, attrs in g.edges(data=True)],
    }


def _endpoint_ids(edge, where):
    '''
    The two node IDs from the endpoints of an edge.

    An edge has exactly two endpoints; both are checked for valid IDs like
    node entries.

    The two is fixed here and not in the notation file: a networkx edge has
    two ends and nothing else, a three-ended edge could not be represented at
    all. So a notation cannot choose it.
    '''
    endpoints = edge.get("endpoints")

    if not isinstance(endpoints, list) or len(endpoints) != 2:
        raise GraphInputError(
            f"{where}: 'endpoints' muss eine Liste mit genau 2 Einträgen sein, "
            f"ist {endpoints!r}"
        )

    return tuple(
        require_str_id(require_dict(ep, f"{where}.endpoints[{i}]"),
                       f"{where}.endpoints[{i}]")
        for i, ep in enumerate(endpoints)
    )


def _edge_dict(u, v, attrs):
    '''A networkx edge as an entry in the JSON data format.'''
    edge = {"endpoints": [{"id": u}, {"id": v}]}

    if attrs:
        edge["properties"] = dict(attrs)

    return edge


def _list_at(data, key):
    '''An optional list field from the input data, type-checked.'''
    value = data.get(key, [])

    if not isinstance(value, list):
        raise GraphInputError(
            f"'{key}': muss eine Liste sein, ist {type(value).__name__}"
        )

    return value
