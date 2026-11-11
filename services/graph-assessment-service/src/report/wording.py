'''
How a thing is called in a sentence: type word, label, enumeration, number word.

The small building blocks the two sentence modules build from -- the
sentences about the ops (-> sentences.py) and the sentence per class
instance from the catalog's template (-> templates.py). Nothing here is
about deviations, only about words.

    type_of / name_of   type and label of a node -- also when it only comes
                        into being through an add op ("added")
    headword_of         both together: "Attribut »Marke«"
    ref_name            the label of a reference node
    listing             "steht Attribut »A«" / "stehen »A« und »B«"
    join_and            "a, b und c"
    number_word         small numbers as words

The type word comes from the notation (TYPE_NAMES, node_types); nothing is
inflected -- the sentences are built so that they manage with the base form.

The words are user-facing and stay German.
'''

from src import config
from src.notation import load_notation
from src.notation.diagram import node_label, node_type

#: The word the sentence uses for a node type: "Entität". It is on the node
#: type of the notation (notations/<NOTATION>/<name>.notation.json,
#: node_types), read at import like the units. A type without a word is shown
#: with its own key.
TYPE_NAMES = load_notation(config.NOTATION).type_names()

#: Small numbers as words; larger ones stay digits.
NUMBER_WORDS = {1: "eines", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf"}


def listing(type_name, names):
    '''
    "steht Attribut »A«" or "stehen »A« und »B«".

    The plural of the type word ("Entitäten") cannot be formed from the base
    form, and we do not want to store it -- so the enumeration does not name
    the type. It is in the rest of the sentence anyway.
    '''
    if len(names) == 1:
        return f"steht {TYPE_NAMES.get(type_name, 'Knoten')} {names[0]}"

    return f"stehen {join_and(names)}"

def ref_name(node, ref):
    '''The label of a reference node in quotation marks.'''
    label = node_label(ref.nodes[node]) if node in ref else ""

    return f"»{label or node}«"

def number_word(n):
    '''"eines", "zwei", ... -- from six on the digit.'''
    return NUMBER_WORDS.get(n, str(n))

def headword_of(node, added, ref, sub):
    '''How a unit is addressed: "Attribut »Ort«".'''
    type_name = type_of(node, added, ref, sub)

    return f"{TYPE_NAMES.get(type_name, type_name or 'Knoten')} {name_of(node, added, ref, sub)}"

def type_of(node, added, ref, sub):
    '''The node type -- first among the newly added ones, then over there, then here.'''
    if node in added:
        return str(added[node].get("type", ""))

    if node in sub:
        return node_type(sub.nodes[node])

    if node in ref:
        return node_type(ref.nodes[node])

    return ""

def name_of(node, added, ref, sub):
    '''The label in quotation marks, the ID as a fallback.'''
    if node in added:
        label = added[node].get("properties", {}).get("label", "")
    elif node in sub:
        label = node_label(sub.nodes[node])
    elif node in ref:
        label = node_label(ref.nodes[node])
    else:
        label = ""

    return f"»{label or node}«"

def join_and(names):
    '''"a", "a und b", "a, b und c" -- a readable enumeration.'''
    if len(names) < 2:
        return "".join(names)

    return f"{', '.join(names[:-1])} und {names[-1]}"
