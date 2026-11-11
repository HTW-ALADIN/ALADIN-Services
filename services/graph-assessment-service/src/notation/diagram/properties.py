'''
Read nodes and edges the way the notation means them.

The graph from src/loading carries the raw attributes from the file. Here
what counts according to the notation is read from it:

    node_props   the properties this node type carries, with default and
                 mapped to the equivalence group
    edge_props   the same for the edge, via the type pair of its endpoints
    canonical    such a value, made sortable and hashable

What is not in the schema (coordinates, colours) does not occur. A missing
property returns its default. Equivalent values ("n" and "m") collapse into
one. The label is in none of the answers -- whoever needs it gets it via
node_label.
'''


def node_type(attributes):
    '''The node type as a string. If it is missing, the empty string.'''
    return str(attributes.get("type", ""))


def node_label(attributes):
    '''The label as a string. If it is missing, the empty string.'''
    return str(attributes.get("label", ""))


def node_props(attributes, notation):
    '''
    The comparable properties of a node, normalized.

    Only what the node type may carry according to the notation; an unknown
    type returns an empty dict. Raw values come from node_props_raw.
    '''
    spec = notation.node_types.get(node_type(attributes))

    if spec is None:
        return {}

    return {
        name: normalized(attributes.get(name, ps.default), notation, ps)
        for name, ps in spec.properties.items()
    }


def edge_props(type_u, type_v, properties, notation):
    '''
    The comparable properties of an edge, normalized.

    The selection goes via the type pair of the endpoints: an attribute edge
    cannot carry a cardinality, so none is there.

    "properties" is the attribute dict of exactly this edge and is passed in
    instead of looked up here -- in a MultiGraph "the edge between u and v"
    is not unique.
    '''
    specs = notation.edge_property_specs(type_u, type_v)

    return {
        name: normalized(properties.get(name, ps.default), notation, ps)
        for name, ps in specs.items()
    }


def node_props_raw(attributes, notation):
    '''Like node_props, but not normalized -- for messages and op lists.'''
    spec = notation.node_types.get(node_type(attributes))

    if spec is None:
        return {}

    return {name: attributes.get(name, ps.default) for name, ps in spec.properties.items()}


def edge_props_raw(type_u, type_v, properties, notation):
    '''Like edge_props, but not normalized -- for messages and op lists.'''
    specs = notation.edge_property_specs(type_u, type_v)

    return {name: properties.get(name, ps.default) for name, ps in specs.items()}


def normalized(value, notation, spec=None):
    '''
    Map a value to its equivalence group.

    A value without a group becomes {value} and is thus only equal to
    itself. A tuple spec (the cardinality has two positions) is normalized
    position by position and stays a tuple, so that ("1", "n") and ("n", "1")
    stay different.
    '''
    if spec is not None and spec.tuple is not None:
        if not isinstance(value, (list, tuple)):
            # No tuple where one should be. Do not repair it, just do not
            # break on it -- src/loading/validate.py has reported it.
            return frozenset(notation.equivalents_for(value))

        return tuple(normalized(v, notation, s) for v, s in zip(value, spec.tuple))

    return frozenset(notation.equivalents_for(value))


def canonical(value):
    '''
    Make a normalized value sortable and hashable.

    normalized() returns a frozenset or a tuple of frozensets, depending on
    the spec. Both forms stand at the same position of a signature, and
    sorted() would compare frozenset against tuple (TypeError). Two frozensets
    are also only partially ordered among each other -- "<" is the subset
    relation there, and sorted() would depend on the input order.

    So every value is mapped to nested tuples of strings. The shape tag
    ("set"/"tup"/"val") decides first, the type name comes before the str, so
    that 1 and "1" stay distinguishable. The structure is kept -- a set stays
    a set, a position stays a position.
    '''
    if isinstance(value, (frozenset, set)):
        return ("set", tuple(sorted(canonical(v) for v in value)))

    if isinstance(value, (tuple, list)):
        return ("tup", tuple(canonical(v) for v in value))

    return ("val", type(value).__name__, str(value))
