'''
Search for the piece of the reference solution in the submission.

The full isomorphism probe (-> src/mapping/isomorphism/isomorphic.py) asks
"are both graphs built the same" and answers yes or no. If a single node is
missing in the submission, the answer is no and not a single proven pair is
left -- so on its own it rarely helps.

Here the same question is asked smaller: does THIS piece of the reference
occur in the submission, and right here? The starting point is an exact
name hit that is unique in both directions. From there the piece grows unit
by unit as long as it is found. Where it breaks, that is where the error
sits -- localized, not global.

Three things come out of it, all of equal rank (-> Region below):

    pairs   proven pairs -- under the anchors exactly one partner was possible
    open    groups in which several partners stayed possible. The choice within
            them changes nothing about the structure; it is made by the name
            (-> build.py) and finally by -> src/mapping/interchange.py with
            properties and name similarity. The piece only asks the question narrowly.
    broken  where the growth broke, with what the reference expected there
    stubs   half units in the piece -- not paired, places to repair

What does NOT happen here: nothing is entered into the pairing and nothing is
rewritten. The pairing is built by -> src/mapping/build.py from the regions
(anchors -> piece -> group -> name decides -> again -> softer anchors ->
interchangeable -> rest).

Two rules it shares with the rest:

    Nothing is paired without evidence. A piece "entity with three
    attributes that look alike" has six mappings; the matcher returns one of
    them, arbitrarily. So only what has no alternative under the anchors is
    taken over: exactly one partner that is provably possible
    (-> src/mapping/isomorphism/anchored_probe.py: possible_subgraph_pairs).

    A piece only grows over unclaimed nodes and never overturns a pair.

Without properties: key, cardinality and weakness are not part of the
signature (signature_copy(..., with_properties=False)). They are what the
diff is supposed to find (-> src/report/diff.py); if they were included, a
wrongly set key would not even find its element again. Including them later
would mean a second pass, not a redesign.
'''

from collections import Counter
from dataclasses import dataclass, field

from src.notation.diagram import decompose, node_type, unit_neighbours
from src.mapping.isomorphism import (SIG, anchored_subgraph_probe,
                                     possible_subgraph_pairs, signature_copy)
from src.mapping.labels import exact_label

from .anchors import exact_pairs

#: Why a claim of two regions drops out -- the label in the result.
TWO_PARTNERS = "two regions give it different partners"
TWO_CLAIMANTS = "two reference nodes want the same node"


@dataclass
class Region:
    '''A grown piece of the reference and what it says about the submission.'''

    #: the exact pair it grew from -- (ref, sub)
    seed: tuple = None
    #: the reference nodes of the largest piece that was found
    piece: list = field(default_factory=list)
    #: ref -> sub, proven: under the anchors exactly one partner was possible
    pairs: dict = field(default_factory=dict)
    #: [{"refs": [...], "candidates": [...]}] -- several partners stayed possible.
    #: The list is a lower bound: every entry is provably possible, but there
    #: may be more (-> anchored_probe.py: possible_subgraph_pairs).
    open: list = field(default_factory=list)
    #: [{"at": [...], "expected": {type: count}, "types": {node: type},
    #:   "nodes": [...]}] -- where it broke (-> _site)
    broken: list = field(default_factory=list)
    #: "stubs": unanchored nodes in the piece where something is missing (they
    #: stand at a break). Only half found, so not forced -- their candidates
    #: are in "open", the name may decide.
    stubs: list = field(default_factory=list)

    def __len__(self):
        return len(self.piece)


def find_regions(ref, sub, notation, anchor_match=exact_label,
                 seeds=None, exact_open=False):
    '''
    All regions that grow from the anchors.

    The anchors are the exact name hits (-> anchors.py: exact_pairs,
    "anchor_match" says what counts as equal) -- or, if "seeds" is given,
    exactly these pairs {ref: sub}. That way -> src/mapping/build.py passes
    everything already settled to the search, and the piece grows on from there.

    "exact_open" means: the candidate lists in "open" are complete (every
    candidate checked on its own). Otherwise the check stops at the second
    possible partner -- enough to answer "exactly one?", but the list is then
    only a lower bound. Complete lists cost minutes on large, symmetric
    submissions; whoever uses the groups further needs them that way.

    Returns a list of Region, sorted by their seed node. A seed pair that an
    earlier region already paired with the same partner is skipped -- it
    would walk the same piece a second time.
    '''
    exact = dict(seeds) if seeds is not None else exact_pairs(ref, sub, anchor_match)

    if not exact:
        return []

    # Built once per submission and reused for all pieces.
    ref_copy = signature_copy(ref, notation, with_properties=False)
    host = signature_copy(sub, notation, with_properties=False)
    neighbours = unit_neighbours(ref)
    decomposition = decompose(ref)

    regions = []
    covered = {}

    for r in sorted(exact, key=str):
        if covered.get(r) == exact[r]:
            continue

        piece, pairs, broken, loose = _grow(ref_copy, host, (r, exact[r]), exact,
                                            neighbours, decomposition)
        forced, open_groups, stubs = _harvest(ref, sub, ref_copy, host, piece, pairs,
                                              broken, loose, set(exact.values()), exact_open,
                                              decomposition)

        regions.append(Region(
            seed=(r, exact[r]),
            piece=sorted(piece, key=str),
            pairs={**pairs, **forced},
            open=open_groups,
            broken=broken,
            stubs=stubs,
        ))
        covered.update(regions[-1].pairs)

    return regions


def merged_pairs(regions):
    '''
    The pairs of all regions put together -- (pairs, dropped).

    Two regions can claim the same submission node for different reference
    nodes, or give one reference node different partners. Both are a
    contradiction, and both drop out on both sides -- the same rule as for
    the anchors applies (-> unique.py: mutually_unique): exactly one partner,
    and no other reference node wants the same one. Agreeing overlap is not
    a contradiction and stays.
    '''
    claims = {}
    owners = {}

    for region in regions:
        for r, s in region.pairs.items():
            claims.setdefault(r, set()).add(s)
            owners.setdefault(s, set()).add(r)

    pairs, dropped = {}, []

    for r in sorted(claims, key=str):
        partners = claims[r]

        if len(partners) > 1:
            dropped.append({"ref": r, "candidates": sorted(partners, key=str),
                            "reason": TWO_PARTNERS})
            continue

        s = next(iter(partners))

        if len(owners[s]) > 1:
            dropped.append({"ref": r, "candidates": [s], "reason": TWO_CLAIMANTS})
            continue

        pairs[r] = s

    return pairs, dropped


def merged_broken(regions, pairs):
    '''
    The breaks of all regions put together -- once per reference node.

    The same place shows up in several regions: seen from one anchor the same
    thing is missing as seen from another. And what one region notes as a
    break, another may have found. What remains is what lies in NO piece and
    is paired nowhere -- per node its type and the anchors at which the
    reference expected it (united over all regions).

    Returns [{"node", "type", "at": [...]}], sorted by node.
    '''
    found = set(pairs)

    for region in regions:
        found |= set(region.piece)

    merged = {}

    for region in regions:
        for site in region.broken:
            for node in site["nodes"]:
                if node in found:
                    continue

                entry = merged.setdefault(node, {"node": node, "type": site["types"][node], "at": set()})
                entry["at"] |= set(site["at"])

    return [{**entry, "at": sorted(entry["at"], key=str)}
            for _node, entry in sorted(merged.items(), key=lambda kv: str(kv[0]))]


# --------------------------------------------------------------------------- #
# The growth
# --------------------------------------------------------------------------- #

def _grow(ref_copy, host, seed, exact, neighbours, decomposition):
    '''
    Let a piece grow until nothing fits any more.

    One step adds a ring of units: all nodes that hang on the piece via a
    unit edge (-> src/notation/diagram/units.py: unit_neighbours). First the
    whole ring is tried -- one run instead of many. If it does not fit, it
    goes on group by group (-> _groups: same type, same owner), and whatever
    does not fit is noted as a break instead of stopping the growth:
    otherwise a single hole would cut off everything behind it.

    If a group does not fit as a whole, each member is tried on its own. An
    anchor that fits alone is added -- its name says it is there. Another
    member that fits alone is NOT added but goes to "loose": three attributes
    on two places -- which one is missing is a visible choice, not a finding
    (-> _harvest: candidates, no pair). Whatever does not fit alone either is
    a break.

    Every anchor in the ring is set BEFORE the probe. If one of three
    otherwise identical-looking attributes is called "Geburtsdatum" in both
    diagrams, it is pinned down, and the other two have only two
    possibilities left instead of six. And an anchor that contradicts the
    structure (the name sits somewhere else over there) makes its ring fail
    and becomes a break -- instead of the piece growing first and then no
    longer fitting under its own anchors.

    The partners of foreign anchors are blocked in the host (-> _host_for):
    a piece only grows over unclaimed nodes.

    Returns (piece, pairs, broken, loose).
    '''
    r, s = seed
    piece = {r}
    pairs = {r: s}
    broken = []
    refused = set()
    loose = set()
    blocked = set(exact.values())

    def anchored(nodes):
        '''The anchors so far plus the anchors among "nodes".'''
        return {**pairs, **{a: exact[a] for a in nodes if a in exact and a not in pairs}}

    def fits(nodes, anchors):
        return _fits(ref_copy, _host_for(host, blocked, anchors), nodes, anchors)

    while True:
        ring = set()

        for node in piece:
            ring |= neighbours.get(node, set())

        ring -= piece | refused | loose
        # Unit by unit: a relationship comes with its participants, an IS-A
        # with its entities. Alone it would be half a unit, which fits too
        # many places -- and pulls the rest along in the next ring.
        ring, torn = _whole_units(ring, piece, refused | loose, decomposition)

        for node in sorted(torn, key=str):
            refused.add(node)
            broken.append(_site(ref_copy, piece, {node}, neighbours))

        if not ring:
            break

        added = set()

        if fits(piece | ring, anchored(ring)):
            added = set(ring)
        else:
            for expected, group in _groups(ring, ref_copy, decomposition):
                if fits(piece | added | group, anchored(added | group)):
                    added |= group
                    continue

                # A unit with several targets (IS-A with two subtypes)
                # shrinks instead of tipping over: the anchor with each target
                # on its own, what fits goes in together; the missing target
                # is a break.
                anchor = _unit_anchor(group, decomposition)

                if anchor is not None:
                    targets = group - {anchor}
                    kept = {t for t in sorted(targets, key=str)
                            if fits(piece | added | {anchor, t}, anchored(added | {anchor, t}))}

                    if kept and fits(piece | added | {anchor} | kept, anchored(added | {anchor} | kept)):
                        added |= {anchor} | kept
                        refused |= targets - kept
                        broken.append(_site(ref_copy, {anchor}, targets - kept, neighbours))
                        continue

                # "Fits alone" only counts for nodes that hang on the piece
                # themselves. A participant that only came in as the target of
                # a missing relationship or a missing IS-A has no edge in the
                # pattern -- it would trivially fit anywhere. It goes missing too.
                alone = {node for node in group
                         if neighbours.get(node, set()) & (piece | added)
                         and fits(piece | added | {node}, anchored(added | {node}))}

                for anchor in sorted((a for a in alone if a in exact), key=str):
                    if fits(piece | added | {anchor}, anchored(added | {anchor})):
                        added.add(anchor)

                loose |= alone - added
                rest = group - added - alone

                if not rest:
                    continue

                # Final: what does not fit even alone does not fit later
                # either, when more around it is settled. Without this the same
                # break would show up again in every further round, and the
                # loop would keep running empty.
                refused |= rest
                broken.append(_site(ref_copy, piece | added | (alone - added), rest, neighbours))

        if not added:
            break

        piece |= added
        pairs = anchored(added)

    return piece, pairs, broken, loose


def _site(ref_copy, around, missing, neighbours):
    '''
    A break: what is missing, which type it has, and what it hung on.

    "at" are the nodes from "around" (the piece, plus what was added in this
    round or stayed loose) that the missing ones hang on -- so every break
    has a place. "types" gives the type per node, "expected" counts them.
    '''
    missing = sorted(missing, key=str)
    types = {n: _type_of(ref_copy, n) for n in missing}

    return {
        "at": sorted((n for n in around if neighbours.get(n, set()) & set(missing)), key=str),
        "expected": dict(Counter(types.values())),
        "types": types,
        "nodes": missing,
    }


def _unit_anchor(group, decomposition):
    '''The node of the group whose reference targets are the others -- or None.'''
    anchors = [n for n in group if set(decomposition[n].neighbours) & group]

    return anchors[0] if len(anchors) == 1 else None


def _host_for(host, blocked, pairs):
    '''
    The host without the partners of foreign anchors.

    Every seed partner belongs to its anchor; a piece that did not anchor it
    itself must not grow onto it. A real copy, not a view: the matcher runs
    about three times as long on a view, and the copy costs nothing compared
    to a single probe.
    '''
    own = set(pairs.values())

    return host.subgraph([n for n in host if n not in blocked or n in own]).copy()


def _fits(ref_copy, host, piece, pairs):
    '''Does this piece occur in the submission, with these anchors?'''
    pattern = ref_copy.subgraph(piece).copy()

    return anchored_subgraph_probe(host, pattern, pairs) is not None


def _whole_units(ring, piece, closed, decomposition):
    '''
    Complete the ring to whole units.

    Every ring node brings its reference targets that are not yet in the
    piece along (-> src/notation/diagram/units.py: participants of the
    relationship, entities of the IS-A). A target that has already been
    refused tears its node down with it ("torn"): without participants the
    relationship cannot be found. Returns (whole, torn).
    '''
    whole, torn = set(), set()

    for node in sorted(ring, key=str):
        targets = set(decomposition[node].neighbours) - piece

        if targets & closed:
            torn.add(node)
            continue

        whole |= {node} | targets

    return whole, torn


def _groups(ring, ref_copy, decomposition):
    '''
    Split the ring into groups -- and order the groups.

    A group is what has to be tried together: a node with its new reference
    targets in the ring (the relationship with its participants, the IS-A
    with its entities); the rest by type and the targets already settled. In
    normal operation (-> build.py) the ring is skeleton without attributes;
    a run over the full graph applies the same rule to attributes -- one
    group per owner, so that a missing attribute at one owner does not tear
    down those of another.

    The order is "first what brings the least along": first what needs no
    new targets, then by number of targets -- without a declared order, so
    for every notation with units. Returns [(expected, group)],
    expected = {type: count}.
    '''
    bundled = {}
    seen = set()

    # First the units whose targets are in the ring too (the relationship
    # with its participants): all together. Then the rest, by type and owner.
    for node in sorted(ring, key=str):
        targets = set(decomposition[node].neighbours) & ring

        if targets:
            group = {node} | targets
            bundled[(len(targets), _type_of(ref_copy, node), str(node))] = group
            seen |= group

    for node in sorted(ring - seen, key=str):
        owners = tuple(sorted(set(decomposition[node].neighbours) - ring, key=str))
        bundled.setdefault((0, _type_of(ref_copy, node), str(owners)), set()).add(node)

    return [(dict(Counter(_type_of(ref_copy, n) for n in sorted(group, key=str))), group)
            for _key, group in sorted(bundled.items(), key=lambda kv: kv[0])]


def _type_of(ref_copy, node):
    '''The node type as it is in the signature -- its first position.'''
    return ref_copy.nodes[node][SIG][0]


# --------------------------------------------------------------------------- #
# The harvest
# --------------------------------------------------------------------------- #

def _harvest(ref, sub, ref_copy, host, piece, pairs, broken, loose, blocked,
             exact_open=False, decomposition=None):
    '''
    What the piece found proves -- (forced, open_groups, stubs).

    The matcher returns ONE mapping, chosen arbitrarily among the symmetric
    ones. Taking it over would be guessing. So each candidate pair is asked
    on its own: if exactly one partner stays possible under the anchors, the
    pair is proven; if two stay, it stays open and goes with a narrow
    candidate list to -> src/mapping/build.py (there the name decides, then
    interchange).

    A candidate is every submission node with the same node type -- NOT only
    whoever the one mapping hit. The difference is not cosmetic: if two
    interchangeable attributes hang on the same entity, a mapping always hits
    only one of them, and the other would then look impossible. A choice
    would turn into proof. Nodes already anchored drop out by themselves --
    the probe rejects two anchors on the same node. The partners of foreign
    anchors are blocked (-> _host_for).

    Stubs (-> _stubs) and loose nodes (-> _grow: fit alone, not together)
    are not forced, and the stub is taken out of the pattern before the
    harvest: a relationship without its attributes fits every relationship
    between the same entities, and through such a stub the constraint would
    be passed on to the neighbours. The price: whatever hangs on the stub
    loses its hold in the pattern and gets a broad candidate list -- marked
    and with a follow-up question, instead of silently wrong. Stubs and loose
    nodes only get the cheap pre-check as their candidate list; the name has
    to decide.
    '''
    stubs = _stubs(piece, pairs, broken)
    kept = set(piece) - stubs
    pattern = ref_copy.subgraph(kept).copy()
    view = _host_for(host, blocked, pairs)

    if anchored_subgraph_probe(view, pattern, pairs) is None:
        return {}, [], sorted(stubs, key=str)

    taken = set(pairs.values()) | blocked

    def could_sit(a, b):
        return (b not in taken and node_type(sub.nodes[b]) == node_type(ref.nodes[a])
                and _could_sit_there(pattern, view, a, b))

    candidates = {a: [b for b in sub if could_sit(a, b)] for a in kept if a not in pairs}
    # enough=2: the only question is whether exactly ONE partner remains --
    # from the second one on the answer is settled. With exact_open every
    # candidate is checked; that costs minutes on large, symmetric submissions,
    # but the list is complete and the same from run to run.
    possible = possible_subgraph_pairs(view, pattern, candidates, pairs,
                                       enough=None if exact_open else 2)

    forced = {a: partners[0] for a, partners in possible.items()
              if len(partners) == 1}
    open_cases = {a: partners for a, partners in possible.items()
                  if len(partners) != 1}

    # Whole units: a relationship (an IS-A) is only proven once its reference
    # targets are -- a relationship is determined by its participants. If a
    # participant stays open (two free entities would qualify), the
    # relationship stays open too: with its one candidate, but without force.
    # Otherwise the half pair hides what really stands at that place -- and
    # the relationship the submission drew INSTEAD of the entity is found by
    # nobody any more (FK-6.9). Step 7 in build.py keeps the same rule for the
    # single candidate.
    if decomposition is not None:
        while True:
            settled = set(pairs) | set(forced)
            half = [a for a in forced
                    if any(t not in settled for t in decomposition[a].neighbours)]

            if not half:
                break

            for a in half:
                open_cases[a] = possible[a]
                del forced[a]

    # Stubs and loose nodes: only the pre-check, no probe. A loose node lies
    # outside the piece; for its neighbourhood the reference counts.
    around = ref_copy.subgraph(set(piece) | loose).copy()

    for a in sorted(stubs | loose, key=str):
        open_cases[a] = [b for b in sub
                         if b not in taken and node_type(sub.nodes[b]) == node_type(ref.nodes[a])
                         and _could_sit_there(around, view, a, b)]

    return forced, _bundle(open_cases), sorted(stubs, key=str)


def _stubs(piece, pairs, broken):
    '''
    The nodes in the piece where something is missing -- without the anchors.

    A node at a break is only half found: the relationship without its
    attributes, the entity without its relationships. What still fits there
    is the bare skeleton, and that fits too many places. An anchor stays an
    anchor even if something is missing -- the name proved it, not the structure.
    '''
    return {node for site in broken for node in site["at"]
            if node in piece and node not in pairs}


def _could_sit_there(pattern, host, a, b):
    '''
    Can a lie on b at all? -- the cheap pre-check before the expensive probe.

    Two necessary conditions, both in one pass over the edges: b needs at
    least as many edges as a (parallel edges counted), and among b's
    neighbours there must be one with the same signature for every
    neighbour of a. Both follow from the fact that a's edges must be found
    again in the host; if either is violated, no probe can succeed.

    The point is not elegance but time: a FAILED probe is the expensive one
    -- the matcher has to work through the whole search space to say "no".
    What drops out here drops out without searching. Only what would have
    failed anyway is filtered out; the result does not change.
    '''
    return _neighbour_signatures(pattern, a) <= _neighbour_signatures(host, b)


def _neighbour_signatures(graph, node):
    '''The signatures of the neighbours as a multiset -- parallel edges count.'''
    return Counter(graph.nodes[other][SIG] for _u, other in graph.edges(node))


def _bundle(open_cases):
    '''
    Bundle the reference nodes that face the same choice.

    The same candidate list means: the same choice. The shape is the one
    -> src/mapping/interchange.py expects anyway.
    '''
    bundled = {}

    for a, partners in open_cases.items():
        bundled.setdefault(tuple(partners), []).append(a)

    return [{"refs": sorted(refs, key=str), "candidates": list(candidates)}
            for candidates, refs in sorted(bundled.items(), key=lambda kv: str(kv[0]))]
