'''
All deviations of the submission from the reference, as ops.

The output form is the vocabulary of a correction list -- the same language
a human grader uses to correct:

    {"op": "add",    "id": ..., "type": ..., "properties": {...}}   node
    {"op": "add",    "endpoints": [a, b], "properties": {...}}      edge
    {"op": "remove", "id": ...}                                     node
    {"op": "remove", "endpoints": [a, b]}                           edge
    {"op": "modify", "id"/"endpoints": ..., "properties": {...}}    value differs
    {"op": "modify", "id": ..., "type": ..., "properties": {...}}   type differs

That makes the diff checkable: apply it and see whether the reference comes
out.

Everything depends on the mapping; nothing is paired without evidence:

    reference node without partner  -> add       something is missing there
    submission node without claim   -> remove    something is extra there
    pair with a differing value     -> modify    something wrong is there
    ambiguous                       -> see "ambiguous_as_ops"

Ambiguous nodes are never paired -- a pair needs evidence. What happens
instead is a decision and not a law of nature, so it is a switch
(config.AMBIGUOUS_AS_OPS, -> deviations() below):

    True   the open reference node is written as missing, its candidates as
           extra, and the ops carry the open question along as a group
           ("assumed", below). The list then always leads to the reference
           -- but at these places it says something that is not proven.
    False  no op at all. The diff is incomplete there, and applied it does
           not give the reference. That is the honest form of "I don't know".

The follow-up question to the student comes in both cases
(src/report/glossary.py).

Every change stands on its own: the edges of a removed node also get their
own "remove", even though the node would take them along when applied. That
way the list is complete no matter who reads it -- and it says the same as a
grader who writes the edges down too.

Labels produce no finding (the label is not a property of the notation),
nor do values with the same meaning ("n" against "m", see
notation.equivalents).

The order of the ops is chosen so the list stays applicable: first remove
edges, then remove nodes, then add nodes, then add edges, then the corrections.

Every op rests on a pair of the mapping, and not every pair carries the same
weight. If the structure alone decided (Mapping.ASSUMED_SOURCES) or the
choice among interchangeable candidates was visible in the diff
(Mapping.groups), the op carries its origin along -- "assumed":

    {"pair": [r, s], "source": "anchor"}    the pair is an assumption
    {"group": {"refs", "candidates", "pairs"}}   the op belongs to a choice

Ops on proven pairs or pairs carried by a name carry nothing. Applying and
comparing ignore the addition; the sentences (src/report/sentences.py) say
what they assume -- and what holds if the assumption is wrong.

An "add" carries a second addition: the side it comes from.

    {"ref_id": r}                  the reference node missing here
    {"ref_endpoints": [r1, r2]}    the reference edge missing here

Because "id" and "endpoints" are in the SUBMISSION's namespace -- that is
where the node is created, and if the reference ID is already taken there,
the new node is called "prescription_2" (-> _new_id). Whoever holds the op
against the reference needs the original; without it the verdict would
depend on how the submission assigns its IDs
(-> src/report/catalog/classify.py: _transform_claims).

The same form once more, machine-readable: diff_ops.schema.json next door.
Nobody reads it during a run -- it defines what this module may produce.
'''

from src.notation.diagram import (edge_props, edge_props_raw, node_props, node_props_raw,
                       node_type)
from src.mapping.mapping import ASSUMED_SOURCES


def deviations(ref, sub, mapping, notation, ambiguous_as_ops=True):
    '''
    The deviations of the submission from the reference, as an op list.

    What happens to the cases that stayed open is up to
    "ambiguous_as_ops" (-> config.AMBIGUOUS_AS_OPS):

        True   the open reference node is written as missing, its candidates
               as extra -- marked as an assumption. The list then always
               leads to the reference, but at these places says something
               that is not proven.
        False  no op at all. The diff is incomplete there and does not reach
               the reference -- that is the honest form of "I don't know".
               The follow-up question comes in both cases
               (src/report/glossary.py).
    '''
    open_ref = {entry["ref"] for entry in mapping.ambiguous}
    open_sub = {candidate
                for entry in mapping.ambiguous
                for candidate in entry["candidates"]}

    if ambiguous_as_ops:
        missing = [*mapping.unmatched_ref, *sorted(open_ref, key=str)]
        removed = list(mapping.unmatched_sub)
        skip_ref, skip_sub = set(), set()
    else:
        # Both sides stay untouched: the node gets no "add", its candidates
        # no "remove", and their edges drop out with them.
        missing = list(mapping.unmatched_ref)
        removed = [s for s in mapping.unmatched_sub if s not in open_sub]
        skip_ref, skip_sub = open_ref, open_sub

    new_ids = {r: _new_id(r, sub, mapping) for r in missing}

    # ref node -> the ID it has in the repaired submission.
    # For paired nodes the partner's, for missing ones the newly assigned one.
    sub_ids = {**mapping.pairs, **new_ids}

    edges_removed, edges_added, edges_modified = _edge_ops(
        ref, sub, sub_ids, skip_ref, skip_sub, notation)

    ops = (
        edges_removed
        + [{"op": "remove", "id": s} for s in removed]
        + [_add_node_op(ref, r, new_ids[r], notation) for r in sorted(new_ids, key=str)]
        + edges_added
        + _node_diffs(ref, sub, mapping, notation)
        + edges_modified
    )
    _mark_assumptions(ops, mapping, sub_ids)

    return ops


def _mark_assumptions(ops, mapping, sub_ids):
    '''
    Write the origin onto the ops that rest on an assumption.

    A group (Mapping.groups) comes before the pair: whoever is in a visible
    choice is explained by it. Otherwise the weakest pair the op touches
    counts -- for an edge one of the two ends.
    '''
    source = getattr(mapping, "source", {})
    groups = getattr(mapping, "groups", [])

    # submission ID (or the ID of a node still to be created) -> group
    group_of = {}

    for group in groups:
        for node in group["candidates"]:
            group_of[node] = group

        for r in group["refs"]:
            if r in sub_ids:
                group_of[sub_ids[r]] = group

    # The cases that stayed open (Mapping.ambiguous) are the same kind of
    # visible choice, just without assignment ("pairs" empty): the reference
    # node is written as missing, its candidates as extra, and the group says
    # that both together are an open question.
    #
    # Only the candidates this case really removes are named. Two cases can
    # share a candidate, and a candidate may still have been assigned to
    # another reference node after the open round
    # (-> src/mapping/interchange.py); both times "is extra" would otherwise
    # stand at a node the op list does not remove at all.
    paired = getattr(mapping, "taken", set())

    for entry in getattr(mapping, "ambiguous", []):
        candidates = [s for s in entry["candidates"]
                      if s not in paired and s not in group_of]

        if not candidates:
            continue    # nothing to choose -- the reference node is simply missing

        group = {"refs": [entry["ref"]], "candidates": candidates, "pairs": {}}

        for node in candidates:
            group_of[node] = group

        if entry["ref"] in sub_ids:
            group_of.setdefault(sub_ids[entry["ref"]], group)

    assumed_pair = {
        s: {"pair": [r, s], "source": source[r]}
        for r, s in getattr(mapping, "pairs", {}).items()
        if source.get(r) in ASSUMED_SOURCES
    }

    for op in ops:
        touched = op["endpoints"] if "endpoints" in op else [op.get("id")]
        group = next((group_of[n] for n in touched if n in group_of), None)

        if group is not None:
            op["assumed"] = {"group": group}
            continue

        pair = next((assumed_pair[n] for n in touched if n in assumed_pair), None)

        if pair is not None:
            op["assumed"] = pair


def _edge_ops(ref, sub, sub_ids, skip_ref, skip_sub, notation):
    '''
    The edge findings: (remove, add, correct).

    Compared node pair by node pair, both sides read in reference IDs. The
    difference in count per pair gives the add and remove ops; values are
    only compared when the reference has exactly one edge and there is
    nothing to guess over there (one edge, or all equal).

    The edges of the removed nodes are included: no reference node has a
    partner there, so they lack a counterpart and become "remove".
    '''
    ref_pairs = _edges_by_pair(ref, sub_ids, skip_ref)
    sub_pairs = _edges_by_pair(sub, None, skip_sub)

    # Back into the reference namespace: sub_ids is one-to-one, every created
    # edge comes from over there, so each of its ends has an original.
    ref_ids = {s: r for r, s in sub_ids.items()}

    remove_ops, add_ops, modify_ops = [], [], []

    for pair in sorted(set(ref_pairs) | set(sub_pairs)):
        here = ref_pairs.get(pair, [])
        there = sub_pairs.get(pair, [])

        for _ in range(len(there) - len(here)):
            remove_ops.append({"op": "remove", "endpoints": list(pair)})

        for i in range(len(here) - len(there)):
            add_ops.append(_add_edge_op(pair, here[i],
                                        [ref_ids.get(end, end) for end in pair]))

        # Compare values where the reference has exactly ONE edge. If there is
        # more than one over there (a recursive relationship as a double
        # edge), the remove ops above take away all but one -- which one stays
        # is not said by the op. So the check runs against EVERY one: if even
        # one differs, the remaining one has to be set to the reference
        # value, and the modify carries it. Whichever edge stays, the right
        # value is there afterwards.
        #
        # The submission edge is read under the REFERENCE types: for a pair
        # with a type change it counts as it stands after the type correction.
        # Under the old types there would e.g. be no cardinality, and the
        # difference would be lost.
        if len(here) == 1 and there:
            expected = edge_props(*here[0][1], here[0][0], notation)
            expected_raw = edge_props_raw(*here[0][1], here[0][0], notation)
            diff = {}

            for properties, _types in there:
                diff.update(_differing_props(
                    expected, edge_props(*here[0][1], properties, notation), expected_raw))

            if diff:
                modify_ops.append(
                    {"op": "modify", "endpoints": list(pair), "properties": diff})

    return remove_ops, add_ops, modify_ops


def _edges_by_pair(graph, sub_ids, skip=frozenset()):
    '''
    The edges of a graph, bundled by node pair.

    With sub_ids the endpoints are rewritten to their names in the
    submission; without (None) they are already right. Nodes from "skip" and
    edges with an endpoint that cannot be named drop out.
    '''
    bundled = {}

    for u, v, properties in graph.edges(data=True):
        if u in skip or v in skip:
            continue

        if sub_ids is not None:
            if u not in sub_ids or v not in sub_ids:
                continue

            pair = (sub_ids[u], sub_ids[v])
        else:
            pair = (u, v)

        types = (node_type(graph.nodes[u]), node_type(graph.nodes[v]))
        bundled.setdefault(tuple(sorted(pair, key=str)), []).append((properties, types))

    return bundled


def _node_diffs(ref, sub, mapping, notation):
    '''
    Paired nodes where a value or the type differs.

    If the type differs, that is a "modify" with the type AND all properties
    of the reference node -- the old type had different ones, which lapse
    with it.
    '''
    ops = []

    for r in sorted(mapping.pairs, key=str):
        s = mapping.pairs[r]
        type_name = node_type(ref.nodes[r])

        if type_name != node_type(sub.nodes[s]):
            ops.append({"op": "modify", "id": s, "type": type_name,
                        "properties": _props_differing_from_default(
                            ref.nodes[r], notation)})
            continue

        diff = _differing_props(
            node_props(ref.nodes[r], notation),
            node_props(sub.nodes[s], notation),
            node_props_raw(ref.nodes[r], notation),
        )

        if diff:
            ops.append({"op": "modify", "id": s, "properties": diff})

    return ops


def _props_differing_from_default(attributes, notation):
    '''
    The properties of a reference node that are not the default anyway.

    What matches the default need not be written -- a grader does not write
    it down either.
    '''
    return {
        name: attributes[name]
        for name, spec in notation.node_types[node_type(attributes)].properties.items()
        if name in attributes and attributes[name] != spec.default
    }


def _differing_props(expected, actual, expected_raw):
    '''
    Which properties differ? -- {name: correct raw value}.

    Compared normalized, returned raw: the op should name the value that
    ought to be there, not the internal normal form.
    '''
    return {
        name: expected_raw[name]
        for name, value in expected.items()
        if name in actual and actual[name] != value
    }


def _add_node_op(ref, r, new_id, notation):
    '''A reference node as it would have to be created in the submission.'''
    attributes = ref.nodes[r]
    properties = {"label": attributes.get("label", ""),
                  **_props_differing_from_default(attributes, notation)}

    return {"op": "add", "id": new_id, "type": node_type(attributes),
            "properties": properties, "ref_id": r}


def _add_edge_op(pair, edge, ref_pair):
    '''A reference edge as it would have to be created in the submission.'''
    properties, _types = edge
    op = {"op": "add", "endpoints": list(pair)}

    if properties:
        op["properties"] = dict(properties)

    op["ref_endpoints"] = list(ref_pair)

    return op


def _new_id(r, sub, mapping):
    '''
    Under which name a missing reference node is created.

    The reference ID if it is free in the submission, otherwise with a
    counter appended. An ID already taken would run into "add node: already
    present" when applied, and the node would still be missing.
    '''
    if r not in sub:
        return r

    # Also what the mapping claims: during a run these are submission nodes
    # and therefore already in it, but claimed is claimed.
    taken = set(sub.nodes) | set(mapping.pairs.values())
    i = 2

    while f"{r}_{i}" in taken:
        i += 1

    return f"{r}_{i}"
