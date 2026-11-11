'''
Assign interchangeable candidates.

The core in plain words: two submission nodes with the same type and the
same neighbours cannot be told apart from the graph. No matter who is
assigned to which reference node -- the repaired graph is the same in the
end. So we assign (source "interchangeable") instead of leaving the question
open. If the candidates look structurally different, nothing is decided
here: the group stays open and ends up in the mapping as "ambiguous"
(-> src/mapping/build.py, step 8).

The technical term behind it is automorphism: a mapping of a graph onto
itself that preserves node types and edges. If an automorphism of the
submission turns two candidates into each other, they cannot be told apart
from the graph. (The choice can still change the feedback sentences: with
one reference node and two such candidates, the other one is called "extra"
afterwards.) This is not checked exactly but through a sufficient
condition: same type and the same neighbours with multiplicity. Then
swapping exactly these two nodes is already an automorphism of the skeleton
-- of the edges without their properties. The properties then only decide
who gets whom within the group.

Two fingerprints carry this:

    _structural_fingerprint  type and neighbour IDs, without any property.
                             Equal means: structurally interchangeable --
                             e.g. two attributes at the same entity.
    _comparable_values       properties and edge properties, without
                             neighbours. Decides within the group who needs
                             the fewest corrections.

Called by the piece search (-> src/mapping/build.py: build_mapping), step 7,
with the open candidates from step 6. What they look like and where they
come from is described with the group itself (-> groups.py: Candidates,
candidates, single) -- this module only assigns.
'''

from itertools import combinations, permutations

from src.notation.diagram import canonical, edge_props, node_label, node_props, node_type

from src.mapping.labels import label_similarity

from .groups import Candidates


def resolve(result, candidates, ref, sub, notation):
    '''
    Assign interchangeable candidates.

    Enters the pairs into result (source "interchangeable") and returns the
    remaining candidates that are still open -- {ref: Candidates}.

    Three outcomes per group:

    a)  The candidates are structurally different -> nothing is decided
        here, the group stays open (becomes "ambiguous" in mapping.py).
    b)  Every reference node gets exactly one candidate -> assign, done. The
        choice changes nothing in the diff but the names.
    c)  More candidates than reference nodes or the other way round -> assign
        anyway (the diff must stay applicable), but the choice is visible in
        the diff: it decides who is "extra" or who is "missing". That is why
        the group then goes into result.groups, and src/report/diff.py marks
        the ops on it as an assumption.
    '''
    open_cases = {}
    # Two groups can share a candidate. Whoever comes first gets it; the
    # order is sorted and therefore reproducible.
    taken = result.taken

    for _key, group in sorted(_groups(candidates, ref).items(),
                              key=lambda kv: sorted(str(r) for r in kv[1])):
        nodes = sorted(group, key=str)
        available = [s for s in sorted(candidates[nodes[0]].matches, key=str)
                     if s not in taken]

        # One reference node, at most one candidate: nothing to swap --
        # stays an open case as before.
        if len(available) < 2 and len(nodes) < 2:
            open_cases[nodes[0]] = Candidates(available, candidates[nodes[0]].source)
            continue

        # Outcome a: the candidates are structurally different -- then the
        # choice is NOT a formality, and we decide nothing.
        if len({_structural_fingerprint(sub, s) for s in available}) > 1:
            for r in nodes:
                open_cases[r] = Candidates(available, candidates[r].source)
            continue

        # Outcomes b and c: assign. -> _assign() below
        pairs = _assign(nodes, available, ref, sub, notation)

        for r in nodes:
            if r not in pairs:
                # Reference nodes without a partner really are missing -- an
                # empty candidate list, so they end up as unmatched_ref and
                # not as ambiguous.
                open_cases[r] = Candidates([], "interchangeable")
                continue

            result.pairs[r] = pairs[r]
            result.source[r] = "interchangeable"
            taken.add(pairs[r])

        # Outcome c, the visible choice: whoever got no place is extra;
        # whoever got no partner is missing. The group is recorded so that
        # src/report/diff.py can mark the ops on it as an assumption.
        # (Without candidates there was nothing to choose.)
        if available and len(available) != len(nodes):
            result.groups.append(
                {"refs": nodes, "candidates": available, "pairs": pairs})

    return open_cases


#: Up to this many candidates AND this many reference nodes every possible
#: assignment is tried; above that greedily, reference node by reference
#: node (-> _assign_greedily() below).
#:
#: Both sides must be capped: the candidates are tried in every order, but
#: also every selection of the reference nodes that get a place. Capping only
#: the candidates, 10 reference nodes on 7 candidates cost
#: C(10,7) * 7! = 604,800 variants instead of the 5040 allowed here. With
#: both at 7, 5040 really is the worst case.
EXHAUSTIVE_UP_TO = 7


def _assign(refs, candidates, ref, sub, notation):
    '''
    The best assignment of a whole group -- {ref: sub}, as many pairs as
    possible.

    The assignment is scored as a whole and not pair by pair: otherwise the
    first reference node takes away the candidate that actually belongs to
    the second ("Vorgang" looks a little like "DatRueckgabe", but "VorgNr"
    a lot). The score: first how many pairs agree in their values (who needs
    the fewest corrections), then the sum of name similarities
    (-> labels/label_match.py: label_similarity()). If two assignments have
    the same score, the one tried first wins -- and because the order is
    sorted, the same input always gives the same result.
    '''
    if len(candidates) > EXHAUSTIVE_UP_TO or len(refs) > EXHAUSTIVE_UP_TO:
        return _assign_greedily(refs, candidates, ref, sub, notation)

    wanted = {r: _comparable_values(ref, r, notation) for r in refs}
    offered = {s: _comparable_values(sub, s, notation) for s in candidates}
    labels_ref = {r: node_label(ref.nodes[r]) for r in refs}
    labels_sub = {s: node_label(sub.nodes[s]) for s in candidates}

    def score(pairs):
        return (sum(wanted[r] == offered[s] for r, s in pairs.items()),
                sum(label_similarity(labels_ref[r], labels_sub[s]) for r, s in pairs.items()))

    slots = min(len(refs), len(candidates))
    best, best_score = {}, None

    for chosen_refs in combinations(refs, slots):
        for chosen_subs in permutations(candidates, slots):
            pairs = dict(zip(chosen_refs, chosen_subs))
            current = score(pairs)

            if best_score is None or current > best_score:
                best, best_score = pairs, current

    return best


def _assign_greedily(refs, candidates, ref, sub, notation):
    '''Reference node by reference node, the best free candidate
    (-> _best_candidate() below).'''
    free = list(candidates)
    pairs = {}

    for r in refs:
        if not free:
            break

        pairs[r] = _best_candidate(r, free, ref, sub, notation)
        free.remove(pairs[r])

    return pairs


def _best_candidate(r, free, ref, sub, notation):
    '''
    The best free candidate for r -- no coin toss.

    The properties count first: who needs the fewest corrections. Then the
    name: who looks most like the reference name (-> labels/label_match.py:
    label_similarity() -- no filter, only an order among candidates the
    structure has already proven interchangeable). If two are still level,
    the first one in sorted order wins -- so the same input always gives the
    same result.
    '''
    wanted = _comparable_values(ref, r, notation)
    matching = [s for s in free
                if _comparable_values(sub, s, notation) == wanted]
    pool = matching or free
    label = node_label(ref.nodes[r])

    return max(pool, key=lambda s: (label_similarity(label, node_label(sub.nodes[s])),
                                    -pool.index(s)))


def _groups(candidates, ref):
    '''
    Bundle the reference nodes that face the same choice.

    The key is (structural fingerprint -> _structural_fingerprint() below,
    candidate set) -- only whoever agrees in both really faces the same choice.
    '''
    bundled = {}

    for r, found in candidates.items():
        key = (_structural_fingerprint(ref, r), tuple(sorted(found.matches, key=str)))
        bundled.setdefault(key, []).append(r)

    return bundled


def _structural_fingerprint(graph, node):
    '''
    The fingerprint of a position in the graph -- type and neighbour IDs.

    Without any property. Two nodes with the same fingerprint hang on the
    same neighbours and are therefore structurally interchangeable -- e.g.
    two attributes at the same entity.

    Counted without key: edges(node) yields every parallel edge on its own,
    so the multiplicity is included -- in every graph class a notation may
    choose (-> src/notation/notation.py, graph_class).

    If the notation has a direction, it counts too: edges(node) there only
    yields the outgoing edges, and a node with only incoming ones would
    otherwise look like one without any neighbour -- two of those would
    wrongly be interchangeable. So both directions, and where the edge came
    from is marked at the neighbour.
    '''
    if graph.is_directed():
        around = ([f"->{neighbour}" for _u, neighbour in graph.out_edges(node)]
                  + [f"<-{neighbour}" for neighbour, _v in graph.in_edges(node)])
    else:
        around = [str(neighbour) for _u, neighbour in graph.edges(node)]

    return (node_type(graph.nodes[node]), tuple(sorted(around)))


def _comparable_values(graph, node, notation):
    '''
    The comparable values of a node -- properties and edge properties.

    Without any neighbour. Used to pick, among equivalent candidates, the
    one that needs the fewest corrections.
    '''
    type_name = node_type(graph.nodes[node])
    props = tuple((name, canonical(value))
                  for name, value in sorted(node_props(graph.nodes[node],
                                                       notation).items()))
    edges = tuple(sorted(
        canonical(tuple(sorted(edge_props(type_name, node_type(graph.nodes[neighbour]),
                                          edge, notation).items())))
        for _u, neighbour, edge in graph.edges(node, data=True)
    ))

    return (props, edges)
