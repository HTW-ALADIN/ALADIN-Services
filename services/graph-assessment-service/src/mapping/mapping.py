'''
The pairing: which submission node is which reference node?

Only the data contract lives here: the Mapping that the piece search
(-> src/mapping/build.py: build_mapping) returns and src/report/diff.py
reads.

Nothing is paired without evidence. src/report/diff.py turns
"unmatched_ref" into an "add", "unmatched_sub" into a "remove"; an
"ambiguous" entry becomes add + remove there with a visible assumption --
named, not guessed.

But not every pair is equally certain. If a name decided (exact, label,
semantics, compound), the pair is settled. If the structure alone decided
(ASSUMED_SOURCES below), the pair is an assumption: "Name" at "Kunde" is
probably the reference's "ID" -- or it is not, and then ID is missing and
Name is extra. Both readings lead to the reference; only the student knows
which one is right. That is why every op that rests on such a pair carries
its origin along, and the feedback sentences say what they assume.
-> src/report/diff.py
'''

from dataclasses import dataclass, field

#: The sources where the structure alone decided -- no name confirmed the
#: pair. Ops on such pairs count as an assumption (-> src/report/diff.py).
#: "region" is the growth of the piece search (-> src/mapping/build.py):
#: structure under name anchors, nothing more -- so it is marked, with a
#: follow-up question. "owner": a unique attribute has the same name over
#: there, which says who its owner is -- a neighbour decided, not the node's
#: own name. "interchangeable": structurally interchangeable candidates,
#: assigned at the end (-> interchange.py).
ASSUMED_SOURCES = frozenset({"interchangeable", "region", "owner"})

#: The same sources in order of evidence -- the exact anchor first, the
#: assumptions last (-> build.py). Callers that report pairs sort and count by
#: this order. Unknown sources come after.
SOURCE_ORDER = ["exact", "label", "semantics", "compound", "owner", "region",
                "interchangeable"]


@dataclass
class Mapping:
    '''
    The pairing and everything that stayed open.

    Read by src/report/diff.py -- the diff is built from it.
    '''

    # ref node -> sub node. Only what was unique.
    pairs: dict = field(default_factory=dict)
    # ref node -> where the pair comes from (the step or name stage that
    # decided, -> src/mapping/build.py):
    # "exact" | "label" | "semantics" | "compound" | "owner" | "region" |
    # "interchangeable"
    source: dict = field(default_factory=dict)
    # [{"ref": nid, "candidates": [...]}] -- several possible, none forced.
    # None of it is paired; the diff writes missing + extra with a visible
    # assumption (-> src/report/diff.py).
    ambiguous: list = field(default_factory=list)
    # ref nodes without any candidate -> each becomes an "add"
    unmatched_ref: list = field(default_factory=list)
    # sub nodes nobody claims -> each becomes a "remove"
    unmatched_sub: list = field(default_factory=list)
    # The choices visible in the diff (-> src/mapping/interchange.py: resolve()):
    # more candidates than places or the other way round. Per group
    # {"refs", "candidates", "pairs"} -- whoever is not in "pairs" is extra
    # (candidate) or missing (ref).
    groups: list = field(default_factory=list)

    @property
    def taken(self):
        '''
        The submission nodes that are already assigned.

        The question before every new pair, and therefore the same in every
        step of the pairing: a sub node belongs to exactly one ref node.
        '''
        return set(self.pairs.values())

    @property
    def complete(self):
        '''
        Every reference node has a partner, and nothing is left over.

        The invariant behind the diff: only on a complete pairing does the op
        list have to reach the reference.
        '''
        return not (self.ambiguous or self.unmatched_ref or self.unmatched_sub)

    def take(self, pairs, source):
        '''Enter pairs -- only where both sides are still free.'''
        taken = self.taken

        for r, s in sorted(pairs.items(), key=lambda kv: str(kv[0])):
            if r not in self.pairs and s not in taken:
                self.pairs[r] = s
                self.source[r] = source
                taken.add(s)
