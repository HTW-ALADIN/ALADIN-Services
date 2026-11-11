'''
Isomorphism -- three questions, three files.

    signature.py       What counts as "equal"? -- working copy and predicate
    isomorphic.py      Are the two graphs isomorphic? -- yes/no (start.py)
    anchored_probe.py  Does this piece occur here? -- the anchored proof as a
                       subgraph (-> anchored_subgraph_probe), asked by the
                       growth of the piece search (-> src/mapping/regions.py)

Labels enter none of the three questions.
'''

from .anchored_probe import (anchored_subgraph_probe, anchored_subgraph_witnesses,
                             possible_subgraph_pairs)
from .signature import SIG, same_signature, signature_copy
from .isomorphic import is_isomorphic

__all__ = [
    "SIG",
    "anchored_subgraph_probe",
    "anchored_subgraph_witnesses",
    "is_isomorphic",
    "possible_subgraph_pairs",
    "same_signature",
    "signature_copy",
]
