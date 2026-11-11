'''
The adornments: the attributes go to the partner of their owner.

    6b  one group per paired owner -- its free attributes against the free
        ones at the partner (adornment_groups) --, the name decides
        (-> names.py), and an attribute with exactly one candidate at the
        partner gets it (adorn). Again, until nothing new comes.

An attribute at the wrong owner is therefore in no group: it is missing
there and extra over here -- exactly the trace the error catalog reads for
"attribute attached to the wrong owner". Attributes at an owner without a
partner go missing with it.
'''

from src.notation.diagram import adornment_types, node_type, owner_of

from .groups import candidates, single
from .names import choose_by_name


def adorn(ref, sub, result, switches):
    '''
    Step 6b: the adornments go to the owner -- True if something was added.

    One group per paired owner (its free attributes against the free ones at
    the partner, -> adornment_groups below), the name decides, and an
    attribute with exactly one candidate at the partner gets it -- also so
    that a compound can pull its children along. Again, until nothing new comes.
    '''
    before = len(result.pairs)

    while True:
        adorned = adornment_groups(ref, sub, result)
        chosen = choose_by_name(adorned, ref, sub, result) if switches.with_names else {}
        alone = single(candidates(adorned, ref, result)) if switches.with_growth else {}
        result.take(alone, "region")

        if not chosen and not alone:
            break

    return len(result.pairs) > before


def adornment_groups(ref, sub, result):
    '''
    Step 6b: per paired owner, the free adornments of both sides as a group.

    An attribute at the wrong owner is therefore not in the group of its
    right owner: it is missing there and extra over here -- exactly the trace
    the error catalog reads for "attribute attached to the wrong owner".
    Attributes at an owner without a partner go missing with it.
    '''
    kinds = adornment_types()
    taken = result.taken
    by_owner = {}

    for a in sorted(ref, key=str):
        if node_type(ref.nodes[a]) not in kinds or a in result.pairs:
            continue

        owner = owner_of(ref, a)

        if owner in result.pairs:
            by_owner.setdefault((owner, node_type(ref.nodes[a])), []).append(a)

    groups = []

    for (owner, kind), refs in sorted(by_owner.items(), key=lambda kv: str(kv[0])):
        partner = result.pairs[owner]
        candidates = [b for b in sorted(sub, key=str)
                      if b not in taken and node_type(sub.nodes[b]) == kind
                      and owner_of(sub, b) == partner]
        groups.append({"refs": refs, "candidates": candidates})

    return groups
