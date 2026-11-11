'''
Gates 1 to 4: read the file, check the format, build the graph, check the notation.

    files.py     where the reference and the submissions live
    checks.py    the single checks and GraphInputError
    convert.py   JSON <-> networkx
    load.py      the two entry points
    validate.py  check against the notation

Whatever fails at gates 1 to 3 is rejected. Gate 4 rejects nothing: a
violation is noted, the graph stays.

A rejection names its own rule (REJECTION_RULES), just like a notation
violation does: gate 1 rejects as the wrong kind of diagram -- what cannot
be read is not a notation file --, gates 2 and 3 as a format violation.
'''

from .checks import REJECTION_RULES, GraphInputError, REJECTED, WRONG_KIND
from .load import load_reference, read_graph
from .files import get_reference_path, get_submission_path, iter_all_datasets
from .validate import validate

__all__ = [
    "REJECTION_RULES",
    "GraphInputError",
    "REJECTED",
    "WRONG_KIND",
    "get_reference_path",
    "get_submission_path",
    "iter_all_datasets",
    "load_reference",
    "read_graph",
    "validate",
]
