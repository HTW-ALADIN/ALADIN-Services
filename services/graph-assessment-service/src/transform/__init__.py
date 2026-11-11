'''
Transformations: where the submission builds the same thing differently from the reference.

    pieces.py   what the mapping left open, cut into connected pieces
    match.py    which piece of the submission stands in place of which piece
                of the reference? -- against the declaration
                (-> src/notation/transformations.py); find_transforms is the
                entry point start.py calls after the mapping

A finding changes nothing in the diff. It only says that several deviations
together are ONE decision of the student -- the error catalog reads them as
one instance (-> src/report/catalog) instead of four.

Why this does not go round in circles: the search only sees nodes without a
partner, so it cannot overturn a pair, and it runs once. See match.py.
'''

from .match import Transform, find_transforms
from .pieces import Piece, free_pieces

__all__ = ["Piece", "Transform", "find_transforms", "free_pieces"]
