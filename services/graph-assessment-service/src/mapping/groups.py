'''
The regions turn into groups: who faces the same choice.

    2   from every anchor a piece of the skeleton grows and is searched for as
        a subgraph in the submission (-> regions.py: find_regions); whatever
        has only ONE partner under it is a pair, source "region"
    3   whatever has several partners stands in a group with exactly these
        candidates (grow_from) -- and a structural pair with a different name
        becomes a group if another free node fits by name (name_rivals)

The group is only decided in step 4 (-> names.py).

The same group once more, read the other way round: candidates() turns it
around -- per open reference node its candidates (Candidates) --, and
single() takes from that what is unique in both directions. Both are read by
step 7 (-> build.py, interchange.py); they live here because a group is
created here.
'''

from typing import NamedTuple

from src.notation.diagram import node_label, node_type

from .labels import label_match
from .names import NAME_STAGES
from .regions import find_regions, merged_pairs
from .unique import mutually_unique


class Candidates(NamedTuple):
    '''
    The open candidates of a reference node and who narrowed them down.

    The shape in which step 7 receives the open reference nodes
    (-> build.py, interchange.py: resolve).
    '''

    matches: list
    source: str

def grow_from(ref, sub, notation, result):
    '''
    Steps 2 and 3: the pieces from all pairs so far -- (new pairs, groups).

    For every open reference node, the group is the intersection of its
    candidate lists over all regions in which it is open: every list is a
    necessary condition, so the intersection is one too. Bundled by equal
    list -- whoever faces the same choice stands in one group. Contradictions
    between regions are added as a group, not as a pair.
    '''
    seeds = {r: s for r, s in result.pairs.items() if r in ref and s in sub}
    regions = find_regions(ref, sub, notation, seeds=seeds, exact_open=True)
    grown, dropped = merged_pairs(regions)
    taken = result.taken
    new = {r: s for r, s in grown.items() if r not in result.pairs and s not in taken}

    # A structural pair with a different name becomes a group if another free
    # node of the same type fits by name (-> name_rivals): "Behandl-Zentrum"
    # sits structurally on "Katalog" but has the name of "Zentrum". Then the
    # name decides (step 4), not the structure.
    lists = {}

    for r in sorted(new, key=str):
        rivals = name_rivals(ref, sub, r, new[r], taken | set(new.values()))

        if rivals:
            lists[r] = {new[r]} | rivals

    for r in lists:
        del new[r]

    taken |= set(new.values())

    # Two regions contradict each other (-> merged_pairs: dropped): no pair,
    # but a group -- the candidates of both sides, and the name decides.
    for entry in dropped:
        if entry["ref"] not in result.pairs and entry["ref"] not in new:
            lists[entry["ref"]] = {c for c in entry["candidates"] if c not in taken}

    for region in regions:
        for group in region.open:
            for r in group["refs"]:
                if r in result.pairs or r in new:
                    continue

                free = {c for c in group["candidates"] if c not in taken}
                lists[r] = free if r not in lists else lists[r] & free

    bundled = {}

    for r, candidates in lists.items():
        bundled.setdefault(tuple(sorted(candidates, key=str)), []).append(r)

    groups = [{"refs": sorted(refs, key=str), "candidates": list(candidates)}
              for candidates, refs in sorted(bundled.items(), key=lambda kv: str(kv[0]))]

    return new, groups


def name_rivals(ref, sub, r, s, taken):
    '''
    Free nodes of the same type that fit r by name although the structure
    chose s -- empty if s itself fits by name.

    The cascade is asked without the exact stage (that would already have
    made r an anchor): normalized, synonym, compound -- over all free nodes
    of the same type in the skeleton. That is deliberately wider than the
    group: the skeleton is small (entities, relationships), and a rival only
    turns the structural pair into a group in which the name then has to be
    unique in both directions. The head error of compounds ("Datum" at
    "Geb. Datum") concerns attributes; those do not occur here.
    '''
    label = node_label(ref.nodes[r])
    kind = node_type(ref.nodes[r])
    stages = [getattr(label_match, predicate) for _source, predicate in NAME_STAGES[1:]]

    def fits_name(b):
        return any(same(label, node_label(sub.nodes[b])) for same in stages)

    if fits_name(s):
        return set()

    return {b for b in sub
            if b != s and b not in taken and node_type(sub.nodes[b]) == kind and fits_name(b)}


def candidates(groups, ref, result):
    '''
    The groups turned around: per open reference node its candidates -- {ref: Candidates}.

    The shape step 7 expects (-> interchange.py: resolve). Whoever stands in
    no group has no candidates and is therefore missing.
    '''
    taken = result.taken
    found = {r: Candidates([], "region") for r in ref if r not in result.pairs}

    for group in groups:
        free = [c for c in group["candidates"] if c not in taken]

        for r in group["refs"]:
            if r in found:
                found[r] = Candidates(sorted(free, key=str), "region")

    return found


def single(found):
    '''
    The reference nodes with exactly one candidate that no other has as its only one.

    The same rule as for the anchors (-> unique.py: mutually_unique), only on
    what the structure left over. What comes out here is a pair from
    structure -- source "region", so an assumption (-> build.py).
    '''
    return mutually_unique({r: c.matches for r, c in found.items()})
