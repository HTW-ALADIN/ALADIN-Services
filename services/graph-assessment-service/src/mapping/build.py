'''
The pairing from the pieces -- the way a human grader goes about it.

A grader first looks for a safe anchor (a node with the same name on both
sides), looks from there at what fits around it, and only when two things
look alike does the name decide who is who. That is exactly what happens
here, in eight steps:

    0  skeleton    first without the adornments (-> src/notation/diagram/units.py:
                   skeleton; declared as "adornment": true -- the attributes). The
                   skeleton is entities, relationships, IS-A; it is small, and
                   probing it is cheap. The attributes come in 6b.
    1  anchors     exact name, same type, unique in both directions
                   (-> anchors.py: exact_pairs). Source "exact". Plus 1b: if
                   exactly one attribute "FIN" exists over there, the owners
                   belong together (source "owner"); the attribute itself is
                   then an anchor. Running 1b again in every pass on the free
                   rest brings nothing: the free attributes then hang on owners
                   of another type (type change).
    2  piece       from every anchor a piece of the skeleton grows, unit by
                   unit, and is searched for as a subgraph in the submission
                   (-> regions.py: find_regions). Whatever has only ONE partner
                   under the anchors is a pair -- source "region". If such a
                   pair carries a different name and another free node fits by
                   name, it becomes a group (-> groups.py: name_rivals).
    3  group       whatever has several partners stands in a group with exactly
                   these candidates: the two relationships between "Kunde" and
                   "Auto" against the two over there.
    4  name        within the group the name decides who gets whom -- exact,
       decides     then normalized, then synonym (wordnet), then compound. Only
                   what is unique in both directions is taken. The source is the
                   stage: "exact", "label", "semantics", "compound". So a
                   compound never decides over the whole graph, only among
                   candidates the structure has already bound.
    5  again       every new pair is a new anchor; the piece keeps growing
                   until nothing new comes.
    6  softer      for reference nodes that still have no anchor, normalized
                   names and synonyms may now be anchors -- again only without
                   collision among the nodes still free. Then grow again. Only
                   now, because a soft name can make an exact anchor ambiguous
                   ("Name" against "Bezeichnung").
    6b attributes  one group per paired owner: its free attributes against the
                   free ones at the partner (-> adornments.py), and again the
                   name decides. An attribute at the wrong owner is in no group
                   -- it is missing there and extra over here. Note that the
                   number does not give the order here: in the loop below 6b is
                   tried BEFORE 6. First the attributes at safe owners, and only
                   when those bring nothing either, the soft anchor -- it is the
                   less certain step of the two and so comes last.
    7  rest        whoever is the only one with exactly one candidate gets it
                   (source "region") -- but only as a whole unit: a relationship
                   whose participant is still open stays open (-> _whole_units;
                   the same rule in regions.py, harvest). Whatever looks alike
                   within a group is assigned by -> src/mapping/interchange.py
                   -- the name only orders there (-> label_similarity), source
                   "interchangeable", a visible choice. Whatever looks different
                   stays open.
    8  rest        open with candidates -> "ambiguous", without -> "unmatched_ref",
                   unclaimed over there -> "unmatched_sub". The diff reads that
                   (-> src/report/diff.py).

Where the steps live: 1, 1b and 6 in anchors.py, 2 in regions.py, 3 in
groups.py, 4 in names.py, 6b in adornments.py, 7 in interchange.py. Only the
sequence lives here -- the skeleton (0), the loop (5), the rest (8) -- and
the switches.

No type changes: a node with the wrong type is a break here, not a pair.
That belongs to the repair (transformations, equivalence), not to the
pairing.

What "proven" means here: a pair from step 1 or 4 carries a name. A pair
from step 2 carries only the structure under name anchors -- it counts as an
assumption (-> src/mapping/mapping.py: ASSUMED_SOURCES) and gets a follow-up
question, so that a "Kunde" called "Vermietung" over there never passes
silently.
'''

from dataclasses import dataclass

from src.notation.diagram import owner_of, references, skeleton

from . import interchange
from .adornments import adorn, adornment_groups
from .anchors import exact_pairs, soft_anchors, unique_adornments
from .groups import candidates, grow_from, single
from .labels import label_match
from .mapping import Mapping
from .names import choose_by_name, name_the_pairs


@dataclass(frozen=True)
class RegionSwitches:
    '''All switches, all on. One field per step, so single steps can be switched off (e.g. in tests).'''

    with_adornments: bool = True    # steps 1b and 6b: the adornments (attributes)
    with_growth: bool = True        # steps 2 and 3: piece and groups, and the
    #                                 single candidate from step 7
    with_names: bool = True         # step 4: the name decides within the group
    with_passes: bool = True        # step 5: grow again
    with_soft_anchors: bool = True  # step 6: softer anchors for the rest
    with_interchange: bool = True   # step 7: assign what is interchangeable


def build_mapping(ref, sub, notation, **switches):
    '''
    Pair the reference with the submission -- the eight steps from the module
    docstring above. Returns the Mapping from src/mapping/mapping.py.

    The switches are the fields of RegionSwitches; all off means "only the
    exact anchors in the skeleton". In normal operation all are on; tests
    switch single ones off.
    '''
    switches = RegionSwitches(**switches)
    result = Mapping()
    # First the skeleton: entities, relationships, IS-A. The adornments
    # (attributes) go to the partners of their owners in step 6b.
    bones_ref, bones_sub = skeleton(ref), skeleton(sub)

    # Step 1, the anchors -- and what a unique attribute says about its owner:
    # if exactly one attribute "FIN" exists over there, its owner is the car.
    result.take(exact_pairs(bones_ref, bones_sub, label_match.exact_label), "exact")

    if switches.with_adornments:
        owners, adornments = unique_adornments(ref, sub)
        result.take(owners, "owner")
        # ... and the attribute itself is an anchor if its owners belong together.
        result.take({a: b for a, b in adornments.items()
                       if owner_of(ref, a) is not None
                       and result.pairs.get(owner_of(ref, a)) == owner_of(sub, b)},
              "exact")

    groups = []

    while True:
        # Steps 2 and 3: piece and groups, from all pairs there are.
        grown = {}

        if switches.with_growth:
            grown, groups = grow_from(bones_ref, bones_sub, notation, result)
            result.take(grown, "region")

        # Step 4: the name decides within the group.
        chosen = choose_by_name(groups, ref, sub, result) if switches.with_names else {}

        # Step 5: if there was something new, the piece grows on from there.
        if (grown or chosen) and switches.with_passes:
            continue

        # Step 6b: the attributes of the paired owners.
        if switches.with_adornments and adorn(ref, sub, result, switches):
            if switches.with_passes:
                continue

        # Step 6: softer anchors for the rest -- and then again. Without
        # "again" all stages still run, just without growth.
        if switches.with_soft_anchors and soft_anchors(bones_ref, bones_sub, result):
            if switches.with_passes:
                continue

            while soft_anchors(bones_ref, bones_sub, result):
                pass

        break

    # Step 6b once more at the end, and the remaining attribute groups go to
    # the assignment together with the skeleton groups.
    if switches.with_adornments:
        adorn(ref, sub, result, switches)
        groups = groups + adornment_groups(ref, sub, result)

    # Step 7: assign what is interchangeable. Whoever stands in a group has
    # candidates; whoever stands nowhere has none. Whoever is the only one
    # with exactly one candidate gets it -- "ambiguous" with one candidate
    # makes no sense to anyone. Source "region": structure, so an assumption.
    found = candidates(groups, ref, result)

    if switches.with_growth:
        result.take(_whole_units(single(found), ref, result), "region")
        found = {r: c for r, c in found.items() if r not in result.pairs}

    if switches.with_interchange:
        found = interchange.resolve(result, found, ref, sub, notation)

    # Finally the reason: a structural pair whose names fit each other carries
    # the name as its source -- it is the better reason, and it is proven.
    name_the_pairs(result, ref, sub)

    # Step 8, the rest -- as in src/mapping/mapping.py.
    result.ambiguous = [
        {"ref": r, "candidates": sorted(c.matches, key=str)}
        for r, c in sorted(found.items(), key=lambda kv: str(kv[0]))
        if c.matches
    ]
    result.unmatched_ref = sorted(
        (r for r, c in found.items() if not c.matches), key=str)
    result.unmatched_sub = sorted(
        (n for n in sub if n not in result.taken), key=str)

    return result


def _whole_units(singles, ref, result):
    '''
    Step 7, the barrier: a structural pair from a single candidate only for
    whole units.

    A relationship is determined by its participants. If one of them is
    missing, "the only free candidate at this anchor" says nothing about it
    -- this is exactly where the relationship would otherwise stand that the
    submission drew INSTEAD of the missing entity (relationship instead of
    entity, FK-6.9), and the transformation search would never see it,
    because the pair hides it. A reference target counts as present if it is
    paired or gets its candidate as the only one in this round itself.
    Whatever gets stuck here stays open -- a candidate, no pairing, follow-up
    question (step 8).
    '''
    settled = set(result.pairs) | set(singles)

    return {r: s for r, s in singles.items()
            if all(target in settled
                   for found in references(ref, r).values()
                   for target in found)}
