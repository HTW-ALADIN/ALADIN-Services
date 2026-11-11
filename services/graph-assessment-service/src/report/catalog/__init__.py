'''
The error catalog: the same ops, read as error classes.

    classify.py   which ops together are ONE error
    instances.py  what becomes of them: the instance, its catalog entry, and
                  the two ranks without ops (naming, notation)
    naming.py     what a finding of the diff is called -- computed, not looked up
    points.py     what it costs -- against the notation's scoring

The entries themselves are in notations/<NOTATION>/<name>.fehlerkatalog.json
and are loaded via src.notation.load_catalog (-> src/notation/catalog.py).
The catalog changes nothing in the diff; it is a reading of it.
'''

from .classify import by_class, classify, classify_rejection
from .instances import NO_ENTRY
from .points import deductions
from .naming import finding_names

__all__ = ["NO_ENTRY", "by_class", "classify", "classify_rejection", "deductions", "finding_names"]
