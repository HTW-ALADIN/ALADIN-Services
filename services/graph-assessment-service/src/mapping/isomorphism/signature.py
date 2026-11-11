'''
What counts as "equal" -- precomputed as a signature.

Not the input graphs are compared but working copies: there every node and
every edge only carries the attribute "sig". It holds what counts for the
comparison -- node type and the properties declared in the notation,
canonicalized. The comparison predicate is then a plain "==".

Precomputed and not a predicate function, because networkx only passes the
attribute dicts of the edges to edge_match, not the types of their endpoints.
Without the endpoint types every edge would get every edge property attached
-- even an attribute edge that cannot carry a cardinality at all.

The label is in no signature. The input graphs are never changed.
'''

from src.notation.diagram import canonical, edge_props, node_props, node_type

# Attribute name of the precomputed signature on a working copy.
SIG = "sig"


def signature_copy(graph, notation, with_properties=True):
    '''
    A copy of the same graph class that only carries signatures.

    Two reasons for the copy: the input graphs must not change, and the
    anchored probe needs a temporary attribute.

    In a MultiGraph the iteration uses keys and the copy is created with the
    same key -- otherwise the signatures of parallel edges would end up on
    the wrong one in turn.

    "with_properties=False" leaves key, cardinality and weakness out of the
    signature; what remains is the bare skeleton of node types and edges.
    The piece search needs that (-> src/mapping): properties are what the
    diff is supposed to find (-> src/report/diff.py), and if they were in the
    signature, a wrongly set key would not even find its element again.
    '''
    copy = graph.__class__()

    for node, attributes in graph.nodes(data=True):
        copy.add_node(node, **{SIG: _node_signature(attributes, notation, with_properties)})

    if graph.is_multigraph():
        for u, v, key, properties in graph.edges(keys=True, data=True):
            copy.add_edge(u, v, key=key,
                          **{SIG: _edge_signature(graph, u, v, properties, notation,
                                                  with_properties)})
    else:
        for u, v, properties in graph.edges(data=True):
            copy.add_edge(u, v,
                          **{SIG: _edge_signature(graph, u, v, properties, notation,
                                                  with_properties)})

    return copy


def same_signature(a, b):
    '''
    The predicate for node_match and edge_match: same signature?

    networkx passes in two different things:

        simple graph   the attribute dict of the one edge, so with SIG in it
        MultiGraph     ALL parallel edges of the node pair, as {key: attrdict}

    In the second case the multiset of signatures is compared, so that the
    multiplicity counts: a reflexive relationship hangs on the same node pair
    twice, and a set comparison would flatten two equal parallel edges into one.

    The two are told apart by the presence of SIG -- an edge dict always has
    it, a {key: ...} container never does.
    '''
    if SIG in a:
        return a[SIG] == b[SIG]

    return (sorted(d[SIG] for d in a.values())
            == sorted(d[SIG] for d in b.values()))


def _node_signature(attributes, notation, with_properties=True):
    '''
    Node signature: type and the properties declared in the notation.

    The type is always included and cannot be switched off -- an entity
    must never be mapped onto an attribute. The properties can be switched
    off (-> signature_copy above).
    '''
    props = node_props(attributes, notation) if with_properties else {}

    return (
        node_type(attributes),
        tuple((name, canonical(value)) for name, value in sorted(props.items())),
    )


def _edge_signature(graph, u, v, properties, notation, with_properties=True):
    '''
    Edge signature: the properties for the type pair of its endpoints.

    The endpoint type itself is not included -- node_match already enforces
    it. Sorting is by property name, not by value: normalized values are
    frozensets and only partially ordered among each other.

    Without properties the empty tuple remains: every edge is then equal to
    every other, and only the skeleton counts.
    '''
    if not with_properties:
        return ()

    type_u = node_type(graph.nodes[u])
    type_v = node_type(graph.nodes[v])
    props = edge_props(type_u, type_v, properties, notation)

    return tuple((name, canonical(value)) for name, value in sorted(props.items()))
