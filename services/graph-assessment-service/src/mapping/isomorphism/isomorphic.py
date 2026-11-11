'''
Are the two graphs built the same? -- yes or no, nothing more.

Not the input graphs are compared but their working copies (-> signature.py):
node type and the properties declared in the notation, plus edge direction
and multiplicity. Labels and IDs do not count; the question is whether there
is a mapping that hits every node exactly once.

A no only says THAT it is different, not where. Where is said by the pairing
(-> src/mapping) and, from it, the diff (-> src/report/diff.py).

start.py asks this for one line in the result. As a pairing on its own it
carries little: a single missing node already makes the answer no.
'''

import networkx as nx

from .signature import same_signature, signature_copy


def is_isomorphic(ref, sub, notation):
    '''Are reference and submission isomorphic? Labels do not count.'''
    return nx.is_isomorphic(signature_copy(ref, notation),
                            signature_copy(sub, notation),
                            node_match=same_signature, edge_match=same_signature)
