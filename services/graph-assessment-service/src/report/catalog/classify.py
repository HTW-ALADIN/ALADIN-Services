'''
The error catalog: which ops of the diff together form ONE error, and what it
is called.

The diff (src/report/diff.py) says THAT something differs -- as a list of
ops, every change on its own. A human grader counts differently: "manager is
missing" is one error to them, even if the relationship "has" and two edges
go missing with it. This module bundles the op list the grader's way. The ops
themselves do not change.

One mechanism for everything: a class CLAIMS ops, and the classes are ranked.
The more specific one takes first; every op is claimed exactly once.

    1  Swaps              the transformations from src/transform: whatever the
                          submission built differently is ONE error, not five.
                          They claim the ops of both their pieces before rank 2
                          even looks. Whether the finding is an error at all is
                          up to the declaration ("allowed",
                          -> src/notation/transformations.py): an allowed
                          transformation stays an instance and claims its ops,
                          but carries the verdict "accepted" -- no deduction, no
                          step, just a note. The name of the declaration IS the
                          catalog ID; what the error is called in the course is
                          under "name" in the catalog, the equivalence verdict is
                          in the declaration, and "verdict" says what becomes of
                          the finding.
    2  Element missing /  an add or remove of a node claims the ops of the
       extra              units that hang on it: its edges, its attributes, the
                          relationship that is not determined without it -- as
                          "consequences"
    3  Property           the remaining modify ops, each under its own name. An
                          ordered property (the cardinality, -> ORDERS) is first
                          bundled per unit: all edges of one relationship are ONE
                          instance, and only comparing all sides tells whether it
                          is too narrow, too loose or swapped (-> _ordered_bundles)
    4  Edge               the remaining edge ops between paired nodes. Bundled
                          first: one edge gone and one added at the same node that
                          claims them are ONE error -- the relationship hangs on
                          the wrong partner (-> _rewired, FK-6.11)
    5  Naming             no ops -- the label verdict per pair
    6  Notation           the violations from src/loading/validate.py

What "hangs on" means is up to the notation and its units
(src/notation/diagram/units.py): an attribute references its owner, a
relationship its participants. If the target of a reference is missing too,
the unit is a consequence of that absence. If several targets are missing,
nothing is inferred: which one would be the root is then a guess -- and this
module guesses as little as the mapping does. The unit stays its own instance.

Every instance points back to its element (ref_element / sub_element) and to
the catalog rule (class). If one of its ops rests on an assumption of the
mapping ("assumed", src/report/diff.py), the instance is marked as resting on
an assumption.

What the catalog does not know gets no class (None) -- and stays in the list,
so the invariant stays visible instead of silently dropping out.

How an instance gets its class: the finding brings its own name, and the name
is the id in the catalog (-> entry_of). The notation check names its rule, the
transformation search its declaration, the label verdict its verdict, and this
module names its own bundle (REWIRED). The ops of the diff bring no name -- an
op is not one -- so theirs is computed (-> naming.py, finding_names). The
catalog never describes an op; it lists names, and which names it lists
decides how closely the comparison looks.
'''

from src import config
from src.loading import REJECTED
from src.notation import load_catalog
from src.notation.diagram import (adornment_types, claims_exclusively, node_type,
                                  references)

from ..apply_ops import apply_ops
from .instances import (elements_of, entry_for_facts, entry_of, facts_of, instance_of,
                      naming_instances, notation_instances, op_instance)

#: The empty graph: the class, and the reason given in the sentence (user-facing text).
EMPTY_GRAPH = "empty_graph"
EMPTY_GRAPH_REASON = "leerer Graph"

#: The orders of the notation (<name>.fehlerkatalog.json, "ordnungen"): per
#: property the values from the narrowest to the widest rank -- cardinality:
#: 1 before n = m. This gives a bundle of similar edge ops its direction
#: (-> _rank_sign).
ORDERS = load_catalog(config.NOTATION).orders

#: The class "relationship attached to the wrong partner": not a finding of the
#: transformation search but a bundle built here (-> _rewired). It is named
#: like every other finding.
REWIRED = "relationship_rewired"


def classify(ops, ref, sub, mapping, violations, notation, catalog, transforms=(), orders=None):
    '''
    The ops of a diff as class instances, plus naming and notation.

    "transforms" are the transformations found (-> src/transform). They take
    first, as rank 1; without them every transformation falls apart into its
    single parts, and the catalog counts four errors where a grader sees one.
    "orders" are the notation's orders (default: ORDERS from
    <name>.fehlerkatalog.json); without an order nothing is bundled, and every
    edge op gets its own name.

    Returns a list of dicts:

        class          the catalog ID, None without an entry
        code           the external code of the class (FK-g.n)
        name           its name
        ref_element    the element in the reference (node, edge pair) or None
        sub_element    the same in the submission
        claims         the ops this instance claims
        consequences   those of them that only hang on (everything but the root)
        on_assumption  does one of the ops rest on an assumption?
        reason         the verdict (naming), the violation (notation) or the
                       variant (transformation)
        verdict        "error" -- or "accepted" for an allowed transformation
        transformation None, or the equivalence class behind a rank-1 instance:
                       pattern, variant, equivalent, allowed, anchors (reference)
                       and sub_anchors (their partners in the submission)

    Every op is in exactly one instance.
    '''
    ops = list(ops)

    if sub.number_of_nodes() == 0:
        # An empty graph has nothing that could be missing -- it cannot be
        # assessed as a whole. Reading it as 25 missing elements would be true
        # and useless.
        entry = entry_of(catalog, EMPTY_GRAPH)
        return [instance_of(entry, claims=ops, consequences=[], reason=EMPTY_GRAPH_REASON)] if entry else []

    graphs = {"add": apply_ops(sub, ops)[0], "remove": sub, "modify": sub}
    instances = []
    free = set(range(len(ops)))

    # Rank 1: the transformations -- one finding explains both sides at once.
    for transform in transforms:
        claimed = _transform_claims(ops, transform, free)
        free -= set(claimed)
        instances.append(_transform_instance(catalog, ops, transform, claimed, mapping))

    # Rank 2: the elements and what hangs on them.
    for root, members in _element_trees(ops, graphs):
        if root not in free:
            continue

        members = [i for i in members if i in free]
        free -= {root, *members}
        instances.append(op_instance(catalog, ops, root, members, graphs, sub, mapping, notation))

    # Rank 3, bundled: an ordered property (cardinality) per unit it hangs on.
    # The bundle takes the place of its first op; the other members leave
    # the free set.
    bundles = {}

    for anchor, members, facts in _ordered_bundles(ops, free, graphs, sub, notation,
                                                   ORDERS if orders is None else orders):
        bundles[members[0]] = _bundle_instance(entry_for_facts(catalog, facts), ops, members, anchor, sub, mapping)
        free -= set(members[1:])

    # Rank 4, bundled: one edge gone, one added at the same paired node that
    # claims them -- the relationship hangs on the wrong partner (FK-6.11).
    # Only if the catalog knows the pattern; otherwise they stay two edge ops.
    rewired = entry_of(catalog, REWIRED)

    for anchor, members in (_rewired(ops, free, sub) if rewired else ()):
        bundles[members[0]] = _bundle_instance(rewired, ops, members, anchor, sub, mapping)
        free -= set(members[1:])

    # Ranks 3 and 4: whatever is left, op by op -- the signature says what it is.
    for i in sorted(free):
        instances.append(bundles.get(i) or op_instance(catalog, ops, i, [], graphs, sub, mapping, notation))

    instances += naming_instances(catalog, ref, sub, mapping)
    instances += notation_instances(catalog, violations or [])

    return instances


def classify_rejection(catalog, rejection):
    '''
    A rejected submission as an instance -- without a graph, without ops.

    Whatever fails at gates 1 to 3 (-> src/loading) is never compared: there
    is no graph, so there are no ops an instance could claim. The case still
    has a class, and the rejection brings it along -- just like a notation
    violation brings its rule (-> src/loading/checks.py, REJECTION_RULES). The
    reason is the text of the rejection; it fills {grund} in the catalog's
    template.

    Without a catalog entry the list stays empty -- as everywhere here.
    '''
    entry = entry_of(catalog, getattr(rejection, "rule", REJECTED))

    return [instance_of(entry, reason=str(rejection))] if entry else []


def by_class(instances):
    '''
    The instances counted per class -- {class: {instances, claims,
    consequences, on_assumption}}, in order of first appearance.

    Not a pipeline step: nothing counted here is needed by the run. It is a
    summary for callers such as tests. Nothing is filtered -- an instance
    without a class sits under the key None and so stays visible. What a
    finding costs is counted by points.py, which does filter.
    '''
    counted = {}

    for instance in instances:
        row = counted.setdefault(instance["class"],
                                 {"instances": 0, "claims": 0, "consequences": 0, "on_assumption": 0})
        row["instances"] += 1
        row["claims"] += len(instance["claims"])
        row["consequences"] += len(instance["consequences"])
        row["on_assumption"] += int(instance["on_assumption"])

    return counted


# --------------------------------------------------------------------------- #
# Rank 1: the transformations
# --------------------------------------------------------------------------- #

def _transform_claims(ops, transform, free):
    '''
    The op indices this transformation explains.

    The reference piece is missing from the submission ("add"), the submission
    piece is extra ("remove"); the edges go along as soon as one end lies in
    the respective piece. A correction at a paired node ("modify") is not part
    of it -- the transformation says nothing about it.
    '''
    sides = {"add": set(transform.ref_nodes), "remove": set(transform.sub_nodes)}
    claimed = []

    for i, op in enumerate(ops):
        side = sides.get(op["op"])

        if i not in free or side is None:
            continue

        # The question is asked on the side the piece comes from. An "add"
        # stands for a reference node but carries an ID in the submission's
        # namespace -- if the reference ID is already taken there, the new node
        # is called "prescription_2" (-> src/report/diff.py: _new_id). So the
        # comparison uses ref_id or ref_endpoints, which the op carries along;
        # without them the result would depend on how the submission assigns
        # its IDs.
        if "endpoints" in op:
            if any(end in side for end in op.get("ref_endpoints", op["endpoints"])):
                claimed.append(i)
        elif op.get("ref_id", op["id"]) in side:
            claimed.append(i)

    return claimed


def _transform_instance(catalog, ops, transform, claimed, mapping):
    '''
    A transformation as a class instance.

    No consequences: the ops are not root and appendix, together they are the
    one error. The equivalence verdict and the policy are kept structured
    under "transformation" (-> src/notation/transformations.py); "verdict"
    draws the conclusion every reader needs from them: error or accepted.
    '''
    entry = entry_of(catalog, transform.name)
    transformation = {
        "pattern": transform.name,
        "variant": transform.variant,
        "equivalent": transform.equivalent,
        "allowed": transform.allowed,
        "anchors": list(transform.anchors),
        "sub_anchors": [mapping.pairs[a] for a in transform.anchors if a in mapping.pairs],
    }

    return instance_of(entry,
                     claims=[ops[i] for i in claimed],
                     consequences=[],
                     ref_element=list(transform.ref_nodes),
                     sub_element=list(transform.sub_nodes),
                     reason=transform.variant or None,
                     verdict="accepted" if transform.allowed else "error",
                     transformation=transformation)


# --------------------------------------------------------------------------- #
# Rank 2: root and consequences
# --------------------------------------------------------------------------- #

def _element_trees(ops, graphs):
    '''
    The add/remove nodes as trees: (root, [members]) per root, in op order.
    Members are the edges of the root, the nodes that hang on it, and their
    edges -- all as op indices.

    A node hangs on another one if its unit references it and the other one
    is missing or extra in the same direction. The graph read for this is the
    one both stand in: for "add" the repaired submission, for "remove" the
    submission itself.
    '''
    node_index = {(op["op"], op["id"]): i for i, op in enumerate(ops)
                  if "endpoints" not in op and op["op"] in ("add", "remove")}

    parent = {}

    for (kind, node), i in node_index.items():
        targets = [t for found in references(graphs[kind], node).values() for t in found]
        parents = {node_index[(kind, t)] for t in targets if (kind, t) in node_index}

        if len(parents) == 1:
            parent[i] = parents.pop()

    children, edges_of = {}, {}

    for i, p in parent.items():
        children.setdefault(p, []).append(i)

    for j, op in enumerate(ops):
        owner = _edge_owner(op, node_index, graphs)

        if owner is not None:
            edges_of.setdefault(owner, []).append(j)

    for root in sorted(node_index.values()):
        if root in parent:
            continue

        members, stack = [], [root]

        while stack:
            node = stack.pop()
            members += edges_of.get(node, [])

            for child in children.get(node, []):
                members.append(child)
                stack.append(child)

        yield root, sorted(members)


def _edge_owner(op, node_index, graphs):
    '''
    Which add/remove node does this edge op belong to? -- the op index, or
    None if both ends are paired nodes (rank 4).

    If both ends are missing, the edge belongs to the end whose unit claims it
    (src/notation/diagram/units.py); if both or neither claim it, to the first.
    '''
    if "endpoints" not in op or op["op"] not in ("add", "remove"):
        return None

    kind = op["op"]
    a, b = op["endpoints"]
    ends = [end for end in (a, b) if (kind, end) in node_index]

    if not ends:
        return None

    if len(ends) == 2:
        graph = graphs[kind]
        end_side = claims_exclusively(node_type(graph.nodes[a]), node_type(graph.nodes[b]))
        ends = [b] if end_side == "b" else [a]

    return node_index[(kind, ends[0])]


# --------------------------------------------------------------------------- #
# Rank 3, bundled: ordered properties per unit
# --------------------------------------------------------------------------- #

def _ordered_bundles(ops, free, graphs, sub, notation, orders):
    '''
    The free modify edge ops with an ordered property, bundled by the node
    whose unit claims the edge (the relationship for its cardinalities): per
    bundle (anchor, [op indices], facts). Instead of expected and actual value
    the facts carry the direction of the bundle:

        narrower   every edge allows at most as much as the reference, one less
        looser     every edge allows at least as much, one more
        mixed      both -- the sides go in opposite directions, so they are swapped

    An op that lacks a value (fact "missing") stays out and goes through the
    signature op by op: cardinality missing, per edge. A deviation without a
    direction -- a value outside the order, a position only the submission
    fills -- counts as one of the remaining cases, so mixed. If no end claims
    the edge, the op is its own bundle.
    '''
    groups = {}

    for i in sorted(free):
        op = ops[i]

        if op["op"] != "modify" or "endpoints" not in op:
            continue

        facts = facts_of(op, graphs, sub, notation)
        name = facts.get("property")

        if name not in orders or facts.get("missing"):
            continue

        sign = _rank_sign(facts.get("expected"), facts.get("actual"), orders[name])

        if sign is None:
            continue

        anchor = _claiming_end(op, sub)
        key = (anchor if anchor is not None else ("edge", i), name)
        groups.setdefault(key, []).append((i, sign))

    for (anchor, name), found in groups.items():
        signs = {sign for _i, sign in found}
        direction = "narrower" if signs == {-1} else "looser" if signs == {1} else "mixed"
        facts = {"op": "modify", "target": "edge", "property": name, "direction": direction}
        yield anchor, [i for i, _sign in found], facts


def _rank_sign(expected, actual, order):
    '''
    How the submission deviates from the reference, measured by the order:
    -1 narrower, +1 looser, 0 without a direction (opposite directions inside
    a tuple, a value outside the order, a position only the submission fills)
    -- the "remaining cases". None means: nothing to compare, because the
    submission lacks a value (-> _missing) or the values are equal by rank.
    '''
    ranks = {value: i for i, group in enumerate(order) for value in group}
    wanted = list(expected) if isinstance(expected, (list, tuple)) else [expected]
    seen = list(actual) if isinstance(actual, (list, tuple)) else [actual]

    if actual is None or len(wanted) != len(seen):
        return None

    deltas, extra = [], False

    for want, have in zip(wanted, seen):
        if want in ("", None):
            extra = extra or have not in ("", None)
            continue

        if have in ("", None):
            return None

        deltas.append(ranks[have] - ranks[want] if want in ranks and have in ranks else None)

    known = [d for d in deltas if d is not None]

    if None in deltas:
        return 0

    if known and all(d <= 0 for d in known) and any(d < 0 for d in known):
        return -1

    if known and all(d >= 0 for d in known) and any(d > 0 for d in known):
        return 1

    if any(d != 0 for d in known):
        return 0

    return 0 if extra else None


def _rewired(ops, free, sub):
    '''
    The free add and remove edge ops, bundled by the paired node whose unit
    claims them -- without adornments (an attribute at the wrong owner is
    FK-6.10 and has no bundle). A bundle only forms where at least one edge is
    missing AND one is extra: the relationship is there, but hangs on the
    wrong partner. Per bundle (anchor, [op indices]).
    '''
    adornments = adornment_types()
    groups = {}

    for i in sorted(free):
        op = ops[i]

        if "endpoints" not in op or op["op"] not in ("add", "remove"):
            continue

        anchor = _claiming_end(op, sub)

        if anchor is None or node_type(sub.nodes[anchor]) in adornments:
            continue

        groups.setdefault(anchor, []).append(i)

    for anchor, members in groups.items():
        if {ops[i]["op"] for i in members} == {"add", "remove"}:
            yield anchor, members


def _claiming_end(op, graph):
    '''
    The end of an edge whose unit claims it (src/notation/diagram/units.py):
    the relationship for the edge to the entity, the attribute for the one to
    its owner. None if both or neither claim it, or if an end is missing.
    '''
    a, b = op["endpoints"]

    if a not in graph or b not in graph:
        return None

    end_side = claims_exclusively(node_type(graph.nodes[a]), node_type(graph.nodes[b]))

    if end_side is None:
        return None

    return a if end_side == "a" else b


def _bundle_instance(entry, ops, members, anchor, sub, mapping):
    '''A bundle as an instance: the ops together are the one error, no consequences; the element is the anchor.'''
    if isinstance(anchor, tuple):
        ref_element, sub_element = elements_of(ops[members[0]], sub, mapping)
    else:
        ref_element, sub_element = elements_of({"id": anchor}, sub, mapping)

    return instance_of(entry, claims=[ops[i] for i in members], consequences=[],
                     ref_element=ref_element, sub_element=sub_element)
