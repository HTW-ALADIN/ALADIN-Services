'''
The anchored probe: does this piece occur here?

Is a pair a possible partner under the anchors already settled? Answered by
an actual isomorphism run.

Anchored instead of enumerating: enumerating all isomorphisms is factorially
many in the symmetric case; the anchored probe answers the same question per
pair in one run. The anchor is set as a temporary attribute that node_match
checks too (-> _anchored()).

The question is asked as a subgraph: anchored_subgraph_probe() does not ask
"are both graphs equal" but "does this piece of the reference occur in the
submission, at this place". So one extra node does not cost the whole
answer. A full probe ("are both graphs built the same, under these
anchors") does not exist here: it only helps where the submission is
isomorphic anyway. -> src/mapping
'''

from contextlib import contextmanager

import networkx as nx

from .signature import SIG, same_signature

# Attribute name of the anchoring. Free of collisions, because the working
# copies do not take over the original attributes at all.
_ANCHOR = "anchor"


@contextmanager
def _anchored(pattern_copy, host_copy, anchors):
    '''
    Stamp the anchors, clear them away afterwards.

    Yields whether all anchors could be set. No means: a node is missing, or
    two anchors want the same node on the other side -- that is not a
    mapping, so no probe can satisfy it.

    Every anchor pair gets its OWN token -- the pattern node itself -- and
    not a shared True. With a shared token two anchors would be
    interchangeable with each other, and the probe would answer a weaker
    question than the one asked.

    "pattern" is the side whose node provides the token (the piece of the
    reference), "host" the other one (the whole submission).
    '''
    stamped_pattern = []
    stamped_host = []
    anchors_hold = True

    try:
        for p, h in anchors.items():
            if p not in pattern_copy or h not in host_copy or h in stamped_host:
                anchors_hold = False
                break

            pattern_copy.nodes[p][_ANCHOR] = p
            host_copy.nodes[h][_ANCHOR] = p
            stamped_pattern.append(p)
            stamped_host.append(h)

        yield anchors_hold
    finally:
        # Exactly once per node: the two lists only hold what was really
        # stamped, and thanks to the double-booking check a node is in them
        # at most once.
        for p in stamped_pattern:
            del pattern_copy.nodes[p][_ANCHOR]

        for h in stamped_host:
            del host_copy.nodes[h][_ANCHOR]


def anchored_subgraph_probe(host_copy, pattern_copy, anchors):
    '''
    Does the pattern occur in the host -- at the place the anchors give?

    "anchors" are settled pairs {pattern_node: host_node}. Returns the
    mapping pattern -> host or None.

    If an extra attribute hangs on the submission's entity, the pattern is
    still found, and the extra attribute later simply becomes "extra".

    The search is node-induced: the host nodes hit must have exactly the
    edges of the pattern among each other. An extra node NEXT TO it does not
    matter, an extra edge IN BETWEEN does -- and rightly so, because that is
    a real difference. That is why subgraph_is_isomorphic() and not
    subgraph_is_monomorphic().

    Expects working copies from signature_copy, not the input graphs -- the
    anchor attribute is set and removed again afterwards (-> _anchored()).
    '''
    with _anchored(pattern_copy, host_copy, anchors) as anchors_hold:
        if not anchors_hold:
            return None

        matcher = _matcher_class(host_copy)(host_copy, pattern_copy,
                                            node_match=_same_signature_and_anchor,
                                            edge_match=same_signature)

        if not matcher.subgraph_is_isomorphic():
            return None

        # networkx maps the FIRST graph onto the second, here host onto
        # pattern. The other direction is needed.
        return {p: h for h, p in matcher.mapping.items()}


def anchored_subgraph_witnesses(host_copy, pattern_copy, anchors, limit):
    '''
    Up to "limit" occurrences of the pattern in the host, each as a mapping pattern -> host.

    Why several: a successful search is fast, a failed one expensive -- the
    matcher has to work through the whole search space to say "no". But
    every occurrence proves every pair in it. So a few occurrences up front
    save many expensive single probes, and for a symmetric piece the first
    ones already show that several partners are possible there.

    Collected within the anchoring: otherwise the iterator would keep running
    after the anchors have long been cleared away.
    '''
    with _anchored(pattern_copy, host_copy, anchors) as anchors_hold:
        if not anchors_hold:
            return []

        matcher = _matcher_class(host_copy)(host_copy, pattern_copy,
                                            node_match=_same_signature_and_anchor,
                                            edge_match=same_signature)
        found = []

        for mapping in matcher.subgraph_isomorphisms_iter():
            found.append({p: h for h, p in mapping.items()})

            if len(found) >= limit:
                break

        return found


#: This many occurrences are collected up front before checking pair by pair
#: (-> possible_subgraph_pairs). More cost hardly anything and save plenty of
#: expensive single probes; a rigid piece has only one anyway.
WITNESSES = 25


def possible_subgraph_pairs(host_copy, pattern_copy, candidates, anchors=None,
                            enough=None):
    '''
    Which of the candidate pairs are possible in the host, under the anchors?

    candidates   {pattern_node: [host_nodes to check]}
    anchors      pairs already settled; None means none

    Returns {pattern_node: [host_nodes proven possible]}. "Possible" means:
    there is an anchor-preserving occurrence of the pattern that maps p onto
    h -- proven by a run, not estimated. On working copies and not on the
    input graphs, because the piece search reuses one host copy for many
    patterns (-> src/mapping).

    The cache does not change the result: a successful probe returns a whole
    mapping, and that is a witness for every pair in it. For the same reason
    a few occurrences are collected up front (-> anchored_subgraph_witnesses).

    "enough=n" stops checking a pattern node as soon as n partners are proven
    possible. That is not a shortcut in the result but in the question:
    whoever wants to know whether exactly ONE partner remains is done after
    the second. The list of such a node is then a lower bound -- every entry
    in it is proven possible, but there may be more.

    The order is fixed (sorted by str), so two runs do the same probes in
    the same sequence.
    '''
    if not candidates:
        return {}

    anchors = anchors or {}
    possible = set()

    for witness in anchored_subgraph_witnesses(host_copy, pattern_copy, anchors,
                                               WITNESSES):
        possible.update(witness.items())

    for p in sorted(candidates, key=str):
        for h in sorted(candidates[p], key=str):
            if (p, h) in possible:
                continue

            if enough is not None and _found_so_far(possible, p, candidates[p]) >= enough:
                break

            witness = anchored_subgraph_probe(host_copy, pattern_copy,
                                              {**anchors, p: h})

            if witness is not None:
                possible.update(witness.items())

    return {
        p: [h for h in sorted(candidates[p], key=str) if (p, h) in possible]
        for p in sorted(candidates, key=str)
    }


def _found_so_far(possible, p, partners):
    '''How many partners of p are already proven possible?'''
    return sum(1 for h in partners if (p, h) in possible)


def _same_signature_and_anchor(a, b):
    '''node_match of the probe: same signature AND same anchor.'''
    return a[SIG] == b[SIG] and a.get(_ANCHOR) == b.get(_ANCHOR)


def _matcher_class(graph):
    '''
    The matcher class for the graph shape, spelled out instead of guessed.

    nx.is_isomorphic picks the simple GraphMatcher for MultiGraphs too --
    correct, because the multiplicity is in the shared feasibility test, just
    silently. Here the class is named so it is readable what is being used.
    '''
    if graph.is_multigraph():
        return (nx.algorithms.isomorphism.MultiDiGraphMatcher
                if graph.is_directed()
                else nx.algorithms.isomorphism.MultiGraphMatcher)

    return (nx.algorithms.isomorphism.DiGraphMatcher if graph.is_directed()
            else nx.algorithms.isomorphism.GraphMatcher)
