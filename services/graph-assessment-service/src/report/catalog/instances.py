'''
A finding becomes an instance: what it is called, what it claims, what it costs.

classify.py decides WHICH ops together form one error (ranks 1 to 4).
This file builds the instance from them -- plus the two ranks that have no ops at all:

    op_instance        one op (with its consequences) as an instance, rank 3
    facts_of           what about an op decides its class -- the name under
                       which the catalog lists it (-> naming.py)
    elements_of        which element of the reference and of the submission
                       an op points back to
    naming_instances   rank 5: the label verdict per pair, without any op
    notation_instances rank 6: the violations from src/loading/validate.py
    instance_of        the shape of an instance -- the dict all of them build
    entry_of           the catalog entry for a class
    entry_for_facts    the entry for a computed name

The name is computed, not looked up: an op does not carry one
(-> naming.py: finding_names). What the catalog does not know gets no class
(None) and still stays in the list -- reported, not scored.
'''

from src.mapping.labels import NAMED_KINDS, label_kind, normal_form
from src.notation.diagram import (edge_props_raw, node_label, node_props_raw, node_type,
                                  references)

from ..glossary import NO_NAME_FITS
from .naming import finding_names


#: The name of an instance the catalog has no entry for (user-facing text).
NO_ENTRY = "ohne Katalogeintrag"

#: What the label verdict (src/mapping/labels/kind.py) is called in the catalog.
#: Three verdicts are the same error -- the name differs; "identical" and
#: "spelling" are left out on purpose, they are not an error. These names hold
#: for every notation, so this module may hand them out.
LABEL_CLASSES = {
    "synonym": "label_differs",
    "compound": "label_differs",
    "different": "label_differs",
    "missing": "label_missing",
}

#: The threshold above that: not a single label fits (-> naming_instances).
NO_NAME_FITS_CLASS = "no_name_fits"

# --------------------------------------------------------------------------- #
# One op as an instance
# --------------------------------------------------------------------------- #

def op_instance(catalog, ops, root, members, graphs, sub, mapping, notation):
    '''The instance for a root op and everything that hangs on it.'''
    op = ops[root]
    entry = entry_for_facts(catalog, facts_of(op, graphs, sub, notation))
    ref_element, sub_element = elements_of(op, sub, mapping)

    return instance_of(entry, claims=[op] + [ops[j] for j in members],
                     ref_element=ref_element, sub_element=sub_element)


def facts_of(op, graphs, sub, notation):
    '''
    The facts of an op -- the input its name is computed from (-> naming.py).

    The node type of an add op is in the op itself; for all others it is in
    the submission. "actual" is the value as the submission carries it, with
    the notation's default where it carries nothing -- a missing "key" is
    "none".
    '''
    kind = op["op"]

    if "endpoints" in op:
        facts = {"op": kind, "target": "edge"}

        if kind == "modify":
            a, b = op["endpoints"]
            types = (node_type(sub.nodes[a]), node_type(sub.nodes[b]))
            specs = notation.edge_property_specs(*types)
            actual = edge_props_raw(*types, _edge_attrs(sub, a, b, op.get("properties")), notation)
            facts.update(_correction(op, actual, specs))

            if "expected" in facts:
                facts["missing"] = _missing(facts["expected"], facts["actual"])

        return facts

    node = op["id"]
    graph = graphs[kind]
    facts = {"op": kind, "target": "node",
             "type": op.get("type") if kind == "add" else node_type(sub.nodes[node])}
    form = _form(graph, node)

    if form:
        facts["form"] = form

    if kind == "modify":
        if "type" in op:
            facts.update({"property": "type", "expected": op["type"],
                          "actual": node_type(sub.nodes[node])})
        else:
            node_spec = notation.node_types.get(node_type(sub.nodes[node]))
            facts.update(_correction(op, node_props_raw(sub.nodes[node], notation),
                                     node_spec.properties if node_spec else {}))

    return facts


def _missing(expected, actual):
    '''
    Does the submission lack a value the reference gives? -- no value at all,
    or, for a tuple, an empty position the reference fills. That is
    "cardinality missing" (FK-5.7), per edge, before any direction.
    '''
    if actual is None:
        return True

    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)) and len(expected) == len(actual):
        return any(want not in ("", None) and have in ("", None) for want, have in zip(expected, actual))

    return False


def _correction(op, actual, specs):
    '''
    What a modify op corrects: the property, the expected value, the actual
    value -- plus the default the notation declares for the property.

    The default is what separates "missing" from "too much": an attribute
    without "key" carries "none", and whoever has "none" instead of "primary"
    did not give the value. Which value that is comes from the notation, not
    from this file (-> naming.py).

    In this notation an op corrects exactly one property; if it carried
    several, the alphabetically first one would count -- it stays one instance.
    '''
    properties = op.get("properties") or {}

    if not properties:
        return {}

    name = sorted(properties)[0]
    spec = (specs or {}).get(name)

    return {"property": name, "expected": properties[name], "actual": actual.get(name),
            "default": getattr(spec, "default", None)}


def _form(graph, node):
    '''
    The shape of a unit: "reflexive" (the same target twice), "ternary"
    (three or more target edges), otherwise None. Read through the notation's
    references, not through the node type -- so it does not depend on the notation.
    '''
    if node not in graph:
        return None

    targets = [t for found in references(graph, node).values() for t in found]
    counts = [graph.number_of_edges(node, t) for t in targets]

    if any(count > 1 for count in counts):
        return "reflexive"

    if sum(counts) >= 3:
        return "ternary"

    return None


def elements_of(op, sub, mapping):
    '''
    What the op points at -- (ref_element, sub_element). A node as an ID, an
    edge as a pair. Whatever does not exist on one side is None.
    '''
    partner = {s: r for r, s in mapping.pairs.items()}

    def ref_of(node):
        return partner.get(node, _ref_node_of(node, mapping))

    if "endpoints" in op:
        a, b = op["endpoints"]
        refs = [ref_of(a), ref_of(b)]
        return (refs if None not in refs else None,
                [a, b] if a in sub and b in sub else None)

    node = op["id"]

    return ref_of(node), node if node in sub else None


def _ref_node_of(node, mapping):
    '''
    The reference node behind a newly assigned ID.

    src/report/diff.py adds a missing node under its reference ID, or with a
    counter appended if that ID is taken. This reads it backwards; a node
    that cannot be explained this way has none. A reference node can be
    missing because it has no partner -- or because it is an open case that
    the diff also writes as missing under config.AMBIGUOUS_AS_OPS.
    '''
    missing = set(mapping.unmatched_ref) | {entry["ref"] for entry in mapping.ambiguous}

    if node in missing:
        return node

    stem, _sep, counter = str(node).rpartition("_")

    if counter.isdigit() and stem in missing:
        return stem

    return None


# --------------------------------------------------------------------------- #
# Ranks 5 and 6: naming and notation
# --------------------------------------------------------------------------- #

def naming_instances(catalog, ref, sub, mapping):
    '''
    The label verdict per pair (src/mapping/labels/kind.py: label_kind) as an
    instance, wherever the catalog has an entry for it -- plus the one
    question about the task when not a single name fits.

    "missing" only counts when the submission leaves the name out; an
    unlabelled reference would not be the student's error.
    '''
    by_verdict = {verdict: entry for verdict, class_id in LABEL_CLASSES.items()
                  for entry in [entry_of(catalog, class_id)] if entry}

    instances, kinds = [], []

    for r, s in mapping.pairs.items():
        ref_label, sub_label = node_label(ref.nodes[r]), node_label(sub.nodes[s])
        kind = label_kind(ref_label, sub_label)
        kinds.append(kind)

        if kind == "missing" and normal_form(sub_label):
            continue

        if kind in by_verdict:
            instances.append(instance_of(by_verdict[kind], ref_element=r,
                                       sub_element=s, reason=kind))

    # The threshold: not a single name fits. Counted over the submission, not
    # over the pairs -- if NOTHING was paired at all (kinds is empty), that is
    # the clearest case, not the most harmless one. Only an empty submission
    # stays silent here; it has its own class.
    entry = entry_of(catalog, NO_NAME_FITS_CLASS)

    if (sub.number_of_nodes()
            and not any(kind in NAMED_KINDS for kind in kinds)
            and entry):
        instances.append(instance_of(entry, reason=NO_NAME_FITS))

    return instances


def notation_instances(catalog, violations):
    '''
    The violations from src/loading/validate.py as instances.

    A violation names its own rule, and the rule is the class -- this only
    looks it up. The element is the part of the message before the colon;
    what the violation really concerns is in "affected".
    '''
    return [instance_of(entry_of(catalog, violation["rule"]),
                      sub_element=violation["text"].split(":")[0],
                      reason=violation["text"])
            for violation in violations]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def instance_of(entry, claims=(), consequences=None, ref_element=None, sub_element=None, reason=None,
              verdict="error", transformation=None):
    '''
    One instance. Without "consequences", everything after the first op is a
    consequence -- the first one is the root. An instance without a root (the
    empty graph) says so explicitly.
    '''
    claims = list(claims)

    return {
        "class": entry["id"] if entry else None,
        "code": entry.get("kennung") if entry else None,
        "name": entry["name"] if entry else NO_ENTRY,
        "ref_element": ref_element,
        "sub_element": sub_element,
        "claims": claims,
        "consequences": claims[1:] if consequences is None else list(consequences),
        "on_assumption": any("assumed" in op for op in claims),
        "reason": reason,
        "verdict": verdict,
        "transformation": transformation,
    }


def entry_of(catalog, class_id):
    '''
    The catalog entry for a finding -- or None if the catalog does not list
    it (then the instance stays without a class and stands out).

    The finding carries the name of its class: the notation check its rule,
    the transformation search its declaration, the label verdict its verdict.
    So the catalog is simply looked up and decides nothing.
    '''
    return next((entry for entry in catalog if entry["id"] == class_id), None)


def entry_for_facts(catalog, facts):
    '''
    The same for an op: it names itself from specific to general
    (-> naming.py), and the catalog takes the first level it lists.

    This way the catalog decides how closely to look, without saying a word
    about ops: "primary key not marked" is its own class there, one ternary
    relationship too many is not -- that falls back to "relationship extra".
    '''
    return next((entry for name in finding_names(facts)
                 for entry in [entry_of(catalog, name)] if entry), None)


def _edge_attrs(graph, u, v, expected=None):
    '''
    The attribute dict of the edge u--v. In a MultiGraph the parallel edge
    that differs from "expected" (the values of the op) -- that is the one the
    op means, just as src/report/diff.py checked it against every parallel
    edge -- otherwise the first.
    '''
    if not graph.is_multigraph():
        return graph[u][v]

    parallel = list(graph[u][v].values())

    for attrs in parallel:
        if expected and any(attrs.get(name) != value for name, value in expected.items()):
            return attrs

    return parallel[0]
