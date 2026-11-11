'''
The labels: do two names say the same thing?

    label_match.py  the four predicates, from the strongest to the weakest
                    evidence (exact_label, same_label, same_meaning,
                    is_compound_of), plus label_similarity (no filter, only
                    an order) -- and the selection: language, profiles,
                    methods, where the knowledge base lives
    kind.py         the verdict per pair (label_kind): the same cascade as a
                    word -- "identical", "spelling", "synonym", ...
    normalization/  normalize labels -- a plain text library
    semantics/      pair labels semantically -- the wordnet: the method
                    (backends/), the loader (resources.py), the compound
                    (compound.py)

Asked by the pairing next door: steps 1 and 6 (-> anchors.py) use the
predicates as an anchor rule, step 4 (-> names.py: NAME_STAGES) lets them
decide within a group. Whoever adds a stage puts the predicate here and
registers it there. The verdict (kind.py) is read by report, catalog and the
transformation search -- after the pairing, never inside it.

The knowledge base itself (the wordnet) lives in -> src/knowledge and is
fetched once before operation; without it the name stage "synonym" drops
out, the rest keeps running.
'''

from .kind import NAMED_KINDS, UNCERTAIN_KINDS, label_kind
from .label_match import (exact_label, is_compound_of, label_similarity,
                          normal_form, same_label, same_meaning)

__all__ = [
    "NAMED_KINDS",
    "UNCERTAIN_KINDS",
    "exact_label",
    "is_compound_of",
    "label_kind",
    "label_similarity",
    "normal_form",
    "same_label",
    "same_meaning",
]
