'''
Gate 4: checking against the notation.

The system takes submissions and reference solutions in the same exchange
format and checks both the same way. Whether a file matches this format is
decided by gates 1 to 3 in src/loading -- whatever fails there is rejected.

This is the fourth gate, and it rejects nothing:

    wire format + structure  (src/loading)  -> REJECTION of the submission
    notation                 (here)         -> VIOLATION in the feedback

A violation of the notation is not a format error but exactly the work that
is to be assessed. Example: a submission connects two entities directly
(car -- compact car) instead of putting a relationship diamond or an IS-A
node in between. The file is formally fine; the diagram is not. Rejecting it
here would drop the submission from assessment instead of reporting the
error back. That is why validate returns a list of violations and raises
nothing.

The check runs against the notation file, read as a Notation
(notations/<NOTATION>/<name>.notation.json). The examples below are ERD;
the code contains no notation name:

    allowed_edges     which edge is allowed between which node types --
                      entity to relationship: yes, entity to entity: no
    node_types        which property may appear on which node and which values
                      it can take -- only an attribute carries a key, only an
                      entity can be weak
    edge_properties   the same for the edge -- the cardinality ("1", "n")
                      belongs on the entity--relationship edge and nowhere else

Plus one rule that does not come from the schema file, because it does not
follow from the allowed edges: a diagram is ONE diagram. If it falls apart
into parts that do not touch each other, either a line is missing or it was
drawn in pieces -- both are a finding, and both can be seen without a
reference solution.

This module does not decide whether a notation requires it: the value lives
in the notation (notations/<NOTATION>/<name>.notation.json, block "regeln")
and comes in as the parameter "connected", just like the schema.

Deliberately not checked:

    label             empty labels are allowed in some notations; only what
                      the notation says is required
    equivalents       that "n" and "m" mean the same only matters when
                      comparing -- for the check both are simply allowed

A violation names the rule it breaks (RULES), not just how it reads:

    {"rule": "edge_not_allowed", "text": "Kante auto-kompaktwagen: ...",
     "affected": ["auto", "kompaktwagen"]}

The rule name is the name under which the error catalog lists the class
(-> notations/<NOTATION>/<name>.fehlerkatalog.json, field "id"). It is
deliberately independent of the notation: "an edge that must not exist
here" exists in every notation, so this module may hand it out without
knowing the catalog. Matching on the text instead would break the catalog
entry silently whenever the wording changes.

The violation text is user-facing and stays German.
'''

import networkx as nx

# Attributes every node carries that do not come from the notation:
# "type" is the node type itself, "label" the caption (see above).
FREE_NODE_FIELDS = {"type", "label"}

#: This many elements of a detached part are named, after that only their
#: count is given. Otherwise a message turns into a list.
NAMES_PER_PART = 3

#: The rules checked here -- one per way of violating the notation. The name
#: does not depend on the notation and is also the class in the error catalog
#: (-> module docstring).
RULES = (
    "edge_not_allowed",           # there is no edge between these node types
    "required_property_missing",  # a required property of the edge is missing
    "unknown_type_or_value",      # a type, property or value the notation does not know
    "graph_disconnected",         # the diagram falls apart into several parts
)

TYPE_CHECKS = {
    "string": lambda value: isinstance(value, str),
    "boolean": lambda value: isinstance(value, bool),
    # In Python bool is an int -- without excluding it, True would be a valid number.
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
}


def validate(graph, notation, connected=True):
    '''
    Check a loaded graph against the notation.

    Returns the list of violations (each with "rule", "text", "affected");
    an empty list means "conforming". The finished graph is checked, not the
    file: only the graph tells which type hangs at which edge end.

    "connected" says whether the notation requires a connected diagram. The
    value is in the "regeln" block of the notation file
    (-> src/notation/notation.py) and is passed in by start.py, like the
    notation itself.
    '''
    violations = []

    for node, attributes in graph.nodes(data=True):
        where = f"Knoten {node!r}"
        type_name = attributes.get("type")

        if type_name not in notation.node_types:
            violations.append(_violation("unknown_type_or_value",
                                        f"{where}: unbekannter Knotentyp {type_name!r}", [node]))
            continue

        allowed = notation.node_types[type_name].properties

        for name, value in attributes.items():
            if name in FREE_NODE_FIELDS:
                continue

            if name not in allowed:
                violations.append(_violation(
                    "unknown_type_or_value",
                    f"{where}: {name!r} steht nicht an einem Knoten vom Typ {type_name!r}", [node]))
            else:
                violations += _check_property(name, value, allowed[name], where, [node])

    # Go through parallel edges one by one: a reflexive relationship hangs on
    # the same node pair twice, and each of the two edges carries its own values.
    if graph.is_multigraph():
        edges = graph.edges(keys=True, data=True)
    else:
        edges = ((u, v, None, properties) for u, v, properties in graph.edges(data=True))

    for u, v, key, properties in edges:
        # With parallel edges "edge u-v" would be ambiguous -- then add the nx key.
        where = f"Kante {u}-{v} (#{key})" if graph.number_of_edges(u, v) > 1 else f"Kante {u}-{v}"

        type_u = graph.nodes[u].get("type")
        type_v = graph.nodes[v].get("type")
        rules = notation.matching_edge_rules(type_u, type_v)

        if not rules:
            violations.append(_violation(
                "edge_not_allowed",
                f"{where}: zwischen {type_u!r} und {type_v!r} ist keine Kante erlaubt", [u, v]))
            continue

        for rule in rules:
            for name in rule.required_properties:
                if name not in properties:
                    violations.append(_violation("required_property_missing",
                                                f"{where}: Pflichtangabe {name!r} fehlt", [u, v]))

        allowed = notation.edge_property_specs(type_u, type_v)

        for name, value in properties.items():
            if name not in allowed:
                violations.append(_violation(
                    "unknown_type_or_value",
                    f"{where}: {name!r} steht nicht an einer Kante {type_u}--{type_v}", [u, v]))
            else:
                violations += _check_property(name, value, allowed[name], where, [u, v])

    violations += _check_connected(graph, connected)

    return violations


def _check_connected(graph, connected):
    '''
    Is the diagram connected? -- one message if it falls apart.

    An ERD is one diagram, not several: a part that has no connection to the
    rest is either a forgotten line (one element hangs alone) or a diagram
    drawn in pieces -- then the same elements often appear more than once.

    This can be checked without a reference solution and so belongs here:
    which part is "the right one" does not matter -- what is reported is THAT
    there are several.

    A single node without any connection does not count as a part: it is a
    loose element, and the diff says anyway that it is out of place
    ("attribute extra", "edge missing"). Only when at least two pieces with
    edges of their own stand side by side is it reported -- then the diagram
    really was drawn in parts.
    '''
    if not connected or graph.number_of_nodes() < 2:
        return []

    # For a directed notation the connection counts without direction: whether
    # a line is missing does not depend on where the arrow points.
    components = nx.weakly_connected_components if graph.is_directed() else nx.connected_components
    parts = sorted(components(graph), key=len, reverse=True)

    if sum(1 for part in parts if graph.subgraph(part).number_of_edges()) < 2:
        return []

    # The largest part counts as the diagram, everything else is detached.
    # With two halves of equal size the choice is arbitrary -- the message
    # says the diagram falls apart anyway, not which half counts.
    detached = [_part_names(graph, part) for part in parts[1:]]

    return [_violation("graph_disconnected",
                      f"Diagramm: zerfällt in {len(parts)} nicht verbundene Teile -- "
                      f"abgetrennt {'; '.join(detached)}",
                      sorted(n for part in parts[1:] for n in part))]


def _part_names(graph, part):
    '''A detached part in words: the first elements, then the count.'''
    names = sorted(str(graph.nodes[n].get("label") or n) for n in part)
    shown = ", ".join(f"»{name}«" for name in names[:NAMES_PER_PART])
    rest = len(names) - NAMES_PER_PART

    return f"{shown} und {rest} weitere" if rest > 0 else shown


def _check_property(name, value, spec, where, affected):
    '''
    Check a single value against its PropertySpec: type, enum, tuple.

    A tuple spec describes a value of fixed arity, each position again as a
    PropertySpec -- the cardinality has two positions, ("1", "n"). So the
    positions run through the same check.

    All three findings are the same rule: a value the notation does not
    know. The text says which of the three it was.
    '''
    if spec.tuple is not None:
        if not isinstance(value, (list, tuple)) or len(value) != len(spec.tuple):
            return [_violation(
                "unknown_type_or_value",
                f"{where}: {name!r}={value!r} muss {len(spec.tuple)} Stellen haben", affected)]

        violations = []

        for i, (part, part_spec) in enumerate(zip(value, spec.tuple)):
            violations += _check_property(f"{name}[{i}]", part, part_spec, where, affected)

        return violations

    violations = []

    if spec.type is not None and not TYPE_CHECKS[spec.type](value):
        violations.append(_violation(
            "unknown_type_or_value",
            f"{where}: {name!r} ist {type(value).__name__}, erwartet {spec.type}", affected))

    if spec.enum is not None and value not in spec.enum:
        violations.append(_violation(
            "unknown_type_or_value",
            f"{where}: {name!r}={value!r} ist nicht in {spec.enum}", affected))

    return violations


def _violation(rule, text, affected):
    '''A violation: which rule, in plain words, and what it concerns.'''
    return {"rule": rule, "text": text, "affected": list(affected)}
