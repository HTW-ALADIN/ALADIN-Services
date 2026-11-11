'''
The name decides: within a group the label decides who gets whom.

    4   Stage by stage (NAME_STAGES: exact, normalized, synonym, compound),
        per stage only what is unique in both directions (choose_by_name).
        A compound therefore never decides over the whole graph, only among
        candidates the structure has already bound.

The name never decides across a type boundary: it only chooses among the
candidates the group has already put together, and those have the same node
type (-> regions.py, groups.py). So an entity is never held against an
attribute, not even semantically. What looks like a type change does not
belong here but to the transformations (-> src/transform).

At the end the structural pairs get the name as their reason where it fits
(name_the_pairs): a node sits fixed by structure, and nobody asked any more
that it has the same name over there -- without this the source would stay
"region", an assumption with a follow-up question.

The predicates come from -> labels/label_match.py, through the module via
getattr, so a test can swap them.
'''

from src.notation.diagram import node_label

from .labels import label_match
from .mapping import ASSUMED_SOURCES
from .unique import mutually_unique

#: The name stages for step 4, from strongest to weakest:
#: (source, predicate in labels/label_match.py).
NAME_STAGES = (("exact", "exact_label"), ("label", "same_label"),
               ("semantics", "same_meaning"), ("compound", "is_compound_of"))


def choose_by_name(groups, ref, sub, result):
    '''
    Step 4: in every group the name decides -- {ref: sub}, already entered.

    Stage by stage (NAME_STAGES), per stage only what is unique in both
    directions: r fits exactly one candidate, and no other reference node of
    the group has the same one as its only hit (the same rule as for the
    anchors, -> unique.py: mutually_unique). A stage runs until it takes
    nothing more -- whoever just had two hits may have only one after the
    assignment. What one stage took is gone for the next. The predicates come
    from src/mapping/labels/label_match.py -- through the module, so a test
    can swap them.
    '''
    chosen = {}
    taken = result.taken

    for group in groups:
        refs = [r for r in group["refs"] if r not in result.pairs]
        free = [c for c in group["candidates"] if c not in taken]

        for source, predicate in NAME_STAGES:
            same = getattr(label_match, predicate)

            while True:
                hits = {r: [c for c in free
                            if same(node_label(ref.nodes[r]), node_label(sub.nodes[c]))]
                        for r in refs}
                # Assign sorted by candidate, not by reference node: that way
                # the order depends on the submission's IDs and not on hash
                # order (determinism).
                accepted = sorted(mutually_unique(hits).items(), key=lambda kv: str(kv[1]))

                for r, c in accepted:
                    result.pairs[r] = c
                    result.source[r] = source
                    chosen[r] = c
                    taken.add(c)
                    refs.remove(r)
                    free.remove(c)

                if not accepted:
                    break

    return chosen


def name_the_pairs(result, ref, sub):
    '''
    Give structural pairs the name as their reason, where it fits.

    The growth often finds a pair before the name does: a node sits fixed by
    structure, and nobody asked any more that it has the same name over
    there. The source would stay "region" -- assumption, follow-up question.
    Here every pair from structure or assignment gets the strongest name
    stage it supports (NAME_STAGES); where none fits, it stays an assumption.
    '''
    for r, s in result.pairs.items():
        if result.source[r] not in ASSUMED_SOURCES:
            continue

        for source, predicate in NAME_STAGES:
            if getattr(label_match, predicate)(node_label(ref.nodes[r]), node_label(sub.nodes[s])):
                result.source[r] = source
                break
