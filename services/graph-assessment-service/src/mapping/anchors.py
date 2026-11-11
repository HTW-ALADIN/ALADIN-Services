'''
The anchors: what is settled without neighbours.

    1   exact name, same type, unique in both directions (exact_pairs) --
        called by -> build.py, and once more as the seed of the piece search
        by -> regions.py
    1b  a unique attribute says who its owner is (unique_adornments): if
        exactly one attribute "FIN" exists over there, the owners belong together
    6   softer anchors for the rest: normalized name, then synonym
        (soft_anchors, SOFT_ANCHORS) -- only late, because a soft name can
        make an exact anchor ambiguous ("Name" against "Bezeichnung")

The predicates come from -> labels/label_match.py, through the module via
getattr, so a test can swap them.
'''

from src.notation.diagram import adornment_types, node_label, node_type, owner_of

from .labels import exact_label, label_match
from .unique import mutually_unique

#: The softer anchors for step 6, in this order. No compound: as an anchor
#: over the whole graph it brings back the head error ("Datum" at
#: "Geb. Datum"); within a group it is safe.
SOFT_ANCHORS = (("label", "same_label"), ("semantics", "same_meaning"))


def exact_pairs(ref, sub, anchor_match=exact_label):
    '''
    The name hits that work as anchors -- {ref: sub}.

    Three conditions: same node type, same name according to anchor_match,
    and unique in both directions. Exactly one candidate for r, and no other
    reference node wants the same one.

    Empty labels do not count: two nodes are not the same just because both
    lack a name.
    '''
    hits = {}

    for r in ref:
        label = node_label(ref.nodes[r])

        if not label.strip():
            continue

        wanted = node_type(ref.nodes[r])
        hits[r] = [s for s in sub
                   if node_type(sub.nodes[s]) == wanted
                   and node_label(sub.nodes[s]).strip()
                   and anchor_match(label, node_label(sub.nodes[s]))]

    return mutually_unique(hits)

def unique_adornments(ref, sub):
    '''
    Step 1b: the unique attributes and what they say about their owners.

    Returns (owners, adornments): "adornments" are the exact attribute pairs
    that are unique on both sides (-> exact_pairs on the adornments);
    "owners" the owner pairs that follow from them -- if exactly one
    attribute "FIN" exists on both sides, their owners belong together. Only
    where both owners have the same type, are not adornments themselves (a
    compound is paired through the group of its owner, not through its
    children) and no second attribute claims something else (the same rule
    as exact_pairs, one level up). The owner gets the source "owner": a
    neighbour decided, not its own name.
    '''
    kinds = adornment_types()
    whole_ref, whole_sub = ref, sub
    adorned_ref = ref.subgraph([n for n in ref if node_type(ref.nodes[n]) in kinds])
    adorned_sub = sub.subgraph([n for n in sub if node_type(sub.nodes[n]) in kinds])
    adornments = exact_pairs(adorned_ref, adorned_sub, label_match.exact_label)
    claims = {}

    for a, b in adornments.items():
        o, p = owner_of(whole_ref, a), owner_of(whole_sub, b)

        if o is None or p is None or node_type(whole_ref.nodes[o]) != node_type(whole_sub.nodes[p]):
            continue

        if node_type(whole_ref.nodes[o]) in kinds:
            continue

        claims.setdefault(o, set()).add(p)

    wanted = {}

    for o, partners in claims.items():
        if len(partners) == 1:
            (p,) = partners
            wanted.setdefault(p, []).append(o)

    owners = {owners[0]: p for p, owners in wanted.items() if len(owners) == 1}

    return owners, adornments


def soft_anchors(ref, sub, result):
    '''
    Step 6: softer anchors for the rest -- True if a stage brought something.

    The same rule as for the exact anchors (-> anchors.py: exact_pairs), only
    with a softer predicate and only among the nodes still free on both
    sides. One stage after the other; the first one that holds wins -- after
    that the piece grows on first.
    '''
    free_ref = ref.subgraph([r for r in ref if r not in result.pairs])
    taken = result.taken
    free_sub = sub.subgraph([s for s in sub if s not in taken])

    for source, predicate in SOFT_ANCHORS:
        found = exact_pairs(free_ref, free_sub, getattr(label_match, predicate))

        if found:
            result.take(found, source)
            return True

    return False
