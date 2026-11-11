'''
The label verdict: how do two labels relate to each other?

    label_kind        one stage of the cascade as a word -- "identical", "synonym", ...
    UNCERTAIN_KINDS   the verdicts the name alone does not support
    NAMED_KINDS       the verdicts where the name speaks for itself

Only the predicates next door are used (-> label_match.py). Every pair gets
the verdict, no matter which filter found it: the structure says who is who
-- isomorphism probe, unit, anchor --, the name says whether one can see it.

It is read after the pairing: by the label list and its follow-up questions
(-> src/report/glossary.py), by the error catalog
(-> src/report/catalog/classify.py), by the transformation search
(-> src/transform/match.py: _names_fit).
'''

from functools import cache

from .label_match import is_compound_of, normal_form, same_label, same_meaning

#: The label verdicts worth a follow-up question: what the name alone does
#: not support. If a stage is added in label_match.py, label_kind is the one
#: place where it is registered.
UNCERTAIN_KINDS = ("synonym", "compound", "different")

#: The verdicts where the name speaks for itself.
NAMED_KINDS = ("identical", "spelling")


# Cached, because the same pair is asked several times in a run: by the
# error catalog, by the label list and by the transformation search (-> the
# readers above). Two strings in, one word out -- and the cascade below is
# pure (normalization and wordnet cache on their own, -> label_match.py).
@cache
def label_kind(ref_label, sub_label):
    '''
    How do two labels relate to each other? -- the cascade from
    label_match.py, from the strongest evidence to the weakest:

        missing     at least one side has no label
        identical   equal character by character
        spelling    the same word, written differently -- "Kunden"/"Kunde"
        synonym     different words, the wordnet knows them as equal
        compound    one is the head of the other ("Datum"/"Mietdatum")
                    or both have the same head ("DatBeginn"/"Mietbeginn")
        different   the name alone does not say it is the same

    Independent of the filter that found the pair: a structurally proven
    pair gets its verdict too.
    '''
    if not (normal_form(ref_label) and normal_form(sub_label)):
        return "missing"

    if ref_label == sub_label:
        return "identical"

    if same_label(ref_label, sub_label):
        return "spelling"

    if same_meaning(ref_label, sub_label):
        return "synonym"

    if is_compound_of(ref_label, sub_label):
        return "compound"

    return "different"
