'''
Compounds: in German the head comes last.

    head_word       the head of a compound -- or the label itself
    is_compound_of  is one label the head of the other?

"Rückgabedatum" (return date) is a "Datum" (date), "Mietbeginn" (rental start)
a "Beginn" (start). The head is not guessed but looked up: the longest tail
that is in the language's lemma list (src/mapping/labels/normalization/lang).
A wordnet is not needed for that -- a compound is morphology, not meaning. As
evidence it still counts as semantics: it says that two different words might
mean the same, and so it is weaker than the label and stronger than the
structure.

Expects normalized labels (lower case, base form); which profile that is is
decided by the caller (src/mapping/labels/label_match.py).
'''


def head_word(label, lemmas):
    '''
    The head of a compound -- or the label itself.

    The longest tail that is in the lemma list is searched for. If the label
    itself is in it, it is its own head. Without a list (a language without a
    lemma list) every label is its own head.
    '''
    if not lemmas or label in lemmas:
        return label

    for cut in range(1, len(label)):
        if label[cut:] in lemmas:
            return label[cut:]

    return label


def is_compound_of(a, b, lemmas):
    '''
    Is one label a compound with the other as its head?

    "Rückgabedatum" to "Datum", in both directions. An empty label is the
    head of nothing.
    '''
    if not (a and b):
        return False

    return head_word(b, lemmas) == a or head_word(a, lemmas) == b


def same_head(a, b, lemmas):
    '''
    Do both labels carry the same head?

    "Behandl-Katalog", "B.-Katalog" and "Behandlungskatalog" are all a
    "Katalog"; "DatBeginn" and "Mietbeginn" both a "Beginn". This way
    abbreviations and renamings on the same base word are recognized without
    abbreviation rules of their own -- the head is looked up, not guessed.

    The head must be a looked-up word, and at least one side must be a real
    compound: if both labels are their own head, "same head" would only be
    "same name", and earlier stages check that.
    '''
    if not (a and b):
        return False

    head_a, head_b = head_word(a, lemmas), head_word(b, lemmas)

    if head_a != head_b or (head_a == a and head_b == b):
        return False

    return head_a in lemmas
