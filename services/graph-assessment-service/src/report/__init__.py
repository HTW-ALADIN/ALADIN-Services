'''
The report: what is collected about one submission.

    diff.py        the diff -- the deviations from the reference, as an op list
    apply_ops.py   the other direction: apply an op list to a graph
    diff_ops.schema.json  what an op list has to look like -- the format
                   diff.py writes. Nothing of it is read during a run; it
                   defines what an op list may be
    sentences.py   the feedback -- the same deviations as sentences, unit by unit
    templates.py   the other way to a sentence: ONE sentence per class
                   instance, from the template the catalog brings
    wording.py     how a thing is called in a sentence -- type word, label, enumeration
    catalog/       the same ops, read as error classes (the error catalog)
    glossary.py    the labels: how students name what is in the reference --
                   and the follow-up questions about what is unproven

Everything here is derived from the mapping (src/mapping) and adds nothing
to it: the op list says THAT something differs; sentences, catalog and label
list are readings of it.

The computing happens here. How the result gets onto the screen is next door
(-> src/terminal_output).
'''

from .apply_ops import apply_ops
from .catalog import NO_ENTRY, deductions, by_class, classify, classify_rejection
from .diff import deviations
from .glossary import FILE_NOTE, observe, open_questions, update_glossary
from .sentences import describe, describe_rejection
from .wording import TYPE_NAMES

__all__ = [
    "FILE_NOTE",
    "NO_ENTRY",
    "TYPE_NAMES",
    "deductions",
    "apply_ops",
    "by_class",
    "classify",
    "classify_rejection",
    "describe",
    "describe_rejection",
    "deviations",
    "observe",
    "open_questions",
    "update_glossary",
]
