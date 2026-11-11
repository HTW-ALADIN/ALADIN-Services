'''
The rule of the package, in one place: only what is unique gets paired.

    mutually_unique   {ref: [candidates]} -> {ref: candidate}

Unique means in both directions: the reference node has exactly one
candidate, and no second reference node wants that candidate as its only
one. A conflict drops out on both sides -- nothing is guessed here.

It is asked in three places, each time with different candidates in front:

    1   the name over the whole graph (-> anchors.py: exact_pairs)
    4   the name within a group, in a loop -- whoever is assigned may make
        the next one unique (-> names.py: choose_by_name)
    7   the candidates the structure left over (-> groups.py: single)

Step 1b is not here (-> anchors.py: unique_adornments): there the owner
pairs that several attributes claim together first count as ONE -- a
different rule that only looks similar.
'''

from collections import Counter


def mutually_unique(hits):
    '''
    The pairs that are unique in both directions -- {ref: candidate}.

    "hits" is the list of candidates per reference node. Whoever has more
    than one drops out; whoever shares its only one with another does too.
    '''
    single = {r: found[0] for r, found in hits.items() if len(found) == 1}
    how_often = Counter(single.values())

    return {r: s for r, s in single.items() if how_often[s] == 1}
