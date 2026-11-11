'''
One sentence per class instance -- from the template the catalog brings.

The other way to a sentence: sentences.py tells the ops unit by unit, here
ONE instance tells itself. Where the catalog has a template for a class
("feedback" in <name>.fehlerkatalog.json), ONE sentence is said per instance
-- a transformation is one line, not twenty.

    told_instances     which op belongs to which instance with a template
    claimless_instances  the instances with a template that no op hangs on
    instance_sentence  the template of an instance, filled
    Slots / placeholders / _slots   the placeholders and what fills them

The slots are filled from the graph, not from the instance alone: {ref} and
{sub} name the elements, {nachbarn} the surroundings, {soll} and {ist} the
values, {stellen} the edges of a bundle. A placeholder without a value renders
empty (-> Slots) -- a template should give a sentence, not an error.

choice_of belongs here too: whether the root op of an instance carries a
visible choice. If it does, sentences.py tells the case itself and the
template stays silent -- the choice says more.

The placeholder names are the notation's vocabulary and stay as they are in
the catalog; the sentence text is user-facing and stays German.
'''

from string import Formatter

from src.notation.diagram import node_label, node_type, owner_of, references

from .wording import TYPE_NAMES, headword_of, join_and, name_of, number_word, ref_name

#: The placeholders of a template (<name>.fehlerkatalog.json, "feedback").
#: Useful when checking a catalog (together with placeholders() below): a
#: placeholder in a template that _slots does not fill would stay in the
#: sentence. On top of these come ref_<type> and sub_<type> for every node type
#: of the notation: the labels of the instance nodes of that type on the
#: respective side. "stellen" are the edges of a bundle, one each with
#: partner, expected and actual value (-> _sites).
SLOTS = frozenset({"ref", "sub", "typ", "owner", "nachbarn", "soll", "ist", "folge",
                   "anker", "name", "klasse", "grund", "stellen"})

#: The sentence for a deviation the catalog gives no class
#: (src/report/catalog/classify.py: "class" None). It is reported, not scored,
#: and the sentence says so.
UNCLASSIFIED_TEMPLATE = "Abweichung an {sub} {ref} ohne Katalogeintrag: nicht automatisch bewertet"

#: The one class whose entry is not told here: the follow-up table lists every
#: differently named pair line by line anyway, and with its "mapping" column
#: says more than one sentence could (-> glossary.py, open_questions). One
#: sentence per pair next to it would repeat the same information -- up to
#: fifteen lines that hide the findings which cost points.
TOLD_BY_TABLE = frozenset({"label_differs"})

#: What a transformation sentence adds -- by verdict and equivalence
#: (-> src/report/catalog/classify.py, src/notation/transformations.py).
#: "ja" is the equivalence value from the notation file.
ACCEPTED_PREFIX = "Hinweis: "
EQUIVALENCE_NOTES = {
    "accepted": " -- gleichwertig, im Kurs zugelassen",
    "ja": " -- formal gleichwertig, im Kurs nicht zugelassen",
}


def choice_of(group):
    '''
    The visible choice this unit belongs to -- or None.

    Only if the node itself is extra or missing (add/remove). A correction at
    an assigned node stays a sentence of its own.
    '''
    node_op = next((op for op in group if "endpoints" not in op), None)

    if node_op is None or node_op.get("op") not in ("add", "remove"):
        return None

    return node_op.get("assumed", {}).get("group")

def told_instances(instances, catalog):
    '''
    Which op belongs to which instance with a template -- {id(op): (instance, template)}.

    An instance is only told here if it claims ops and its root op carries no
    visible choice: the choice has its own sentence (-> _choice_sentence), and
    that one says more. Whatever claims no op at all is handled next door
    (-> claimless_instances).
    '''
    templates = {entry.get("id"): entry.get("feedback") or "" for entry in catalog}
    claimed_by = {}

    for instance in instances:
        template = _template_of(instance, templates, catalog)
        claimed = instance.get("claims") or []

        if not template or not claimed or choice_of(claimed[:1]) is not None:
            continue

        for op in claimed:
            claimed_by[id(op)] = (instance, template)

    return claimed_by

def claimless_instances(instances, catalog):
    '''
    The instances with a template that claim no op -- [(instance, template)].

    Two ranks report something without an op hanging on it: the notation
    finding (FK-2.x) objects to the graph itself, the label verdict (FK-8.x)
    to the name of a paired node -- nothing is changed, so there is nothing
    told_instances() could attach its sentence to. It therefore hangs on the
    instance itself, and describe() says it first. Except what the table
    already lists (-> TOLD_BY_TABLE).
    '''
    templates = {entry.get("id"): entry.get("feedback") or "" for entry in catalog}
    pairs = []

    for instance in instances:
        template = _template_of(instance, templates, catalog)

        if not template or instance.get("claims") or instance.get("class") in TOLD_BY_TABLE:
            continue

        pairs.append((instance, template))

    return pairs

def _template_of(instance, templates, catalog):
    '''
    The template for the class of this instance, or "".

    An instance without a class gets the sentence that it is not scored
    automatically (UNCLASSIFIED_TEMPLATE) -- as long as there is a catalog at all.
    '''
    class_id = instance.get("class")

    return templates.get(class_id) or (UNCLASSIFIED_TEMPLATE if class_id is None and catalog else "")

def instance_sentence(instance, template, added, ref, sub):
    '''The template of the class, filled -- plus what the finding adds.'''
    text = template.format_map(Slots(_slots(instance, added, ref, sub)))
    text = " ".join(text.split())   # an empty placeholder leaves no gap
    transformation = instance.get("transformation") or {}

    if instance.get("verdict") == "accepted":
        return ACCEPTED_PREFIX + text + EQUIVALENCE_NOTES["accepted"]

    return text + EQUIVALENCE_NOTES.get(transformation.get("equivalent"), "")

class Slots(dict):
    '''A placeholder the instance does not fill renders empty instead of failing.'''

    def __missing__(self, key):
        return ""

def placeholders(template):
    '''The placeholders of a template -- for checking a catalog.'''
    return {name for _text, name, _spec, _conv in Formatter().parse(template) if name}

def _slots(instance, added, ref, sub):
    '''
    The placeholders of an instance, all as text; whatever does not exist is empty.

    The reference side reads strictly the reference, the submission side
    strictly the submission -- both often carry the same ID.
    '''
    root = (instance.get("claims") or [None])[0]
    ref_element, sub_element = instance.get("ref_element"), instance.get("sub_element")
    transformation = instance.get("transformation") or {}
    slots = {
        "name": instance.get("name") or "",
        "klasse": instance.get("class") or "",
        "grund": instance.get("reason") or "",
        "ref": _element_text(ref_element, ref, added, ref, sub),
        "sub": _element_text(sub_element, sub, added, ref, sub),
        "typ": _element_type(ref_element, sub_element, ref, sub),
        "owner": _around(root, ref_element, sub_element, ref, sub, owner=True),
        "nachbarn": _around(root, ref_element, sub_element, ref, sub, owner=False),
        "soll": _wanted(root),
        "ist": _actual(root, sub),
        "folge": _consequences_text(instance.get("consequences") or [], added, ref, sub),
        "anker": join_and([ref_name(a, ref) for a in transformation.get("anchors", [])]),
        "stellen": _sites(instance, added, ref, sub),
    }

    for side, element, graph in (("ref", ref_element, ref), ("sub", sub_element, sub)):
        for type_name, names in _by_type(element, graph).items():
            slots[f"{side}_{type_name}"] = join_and(names)

    return slots

def _element_text(element, graph, added, ref, sub):
    '''
    A node as its quoted name, an edge pair or a list as an enumeration.
    Whatever is not a node of this graph (the violation text of a notation
    instance) is shown as is; None is empty.
    '''
    if element is None:
        return ""

    if isinstance(element, (list, tuple)):
        return join_and([_element_text(e, graph, added, ref, sub) for e in element])

    if element in graph:
        return f"»{node_label(graph.nodes[element]) or element}«"

    if element in added:
        return name_of(element, added, ref, sub)

    return str(element)

def _element_type(ref_element, sub_element, ref, sub):
    '''How the element is addressed -- from the reference, otherwise from the submission.'''
    for element, graph in ((ref_element, ref), (sub_element, sub)):
        node = element[0] if isinstance(element, (list, tuple)) and element else element

        if isinstance(node, str) and node in graph:
            return TYPE_NAMES.get(node_type(graph.nodes[node]), node_type(graph.nodes[node]))

    return ""

def _around(root, ref_element, sub_element, ref, sub, owner):
    '''
    The owner (owner=True) or all neighbours of the element, as quoted names.

    A missing element stands in the reference, an extra one in the
    submission -- the graph it stands in is read. For edges and corrections
    there is nothing to name.
    '''
    if not root or "endpoints" in root:
        return ""

    if root.get("op") == "add" and isinstance(ref_element, str) and ref_element in ref:
        graph, node = ref, ref_element
    elif root.get("op") == "remove" and isinstance(sub_element, str) and sub_element in sub:
        graph, node = sub, sub_element
    else:
        return ""

    def name(n):
        return node_label(graph.nodes[n]) or str(n)

    if owner:
        found = owner_of(graph, node)
        nodes = [found] if found is not None else []
    else:
        # Sorted by label within a role. Otherwise the order of the node list
        # in the file would count: the same submission, written down in a
        # different order, would say "between A and B" instead of the other
        # way round. The roles themselves keep the notation's order -- that
        # order carries meaning, chance does not.
        nodes = [n for role in references(graph, node).values()
                 for n in sorted(role, key=name)]

    return join_and([f"»{name(n)}«" for n in nodes])

def _wanted(root):
    '''The expected value of the root op: the first property it corrects.'''
    if not root or root.get("op") != "modify":
        return ""

    if "type" in root and "endpoints" not in root:
        return TYPE_NAMES.get(root["type"], root["type"])

    properties = root.get("properties") or {}

    if not properties:
        return ""

    return _value_text(properties[sorted(properties)[0]])

def _actual(root, sub):
    '''The actual value, as the submission carries it -- node, edge or type.'''
    if not root or root.get("op") != "modify":
        return ""

    if "type" in root and "endpoints" not in root:
        node = root.get("id")
        return TYPE_NAMES.get(node_type(sub.nodes[node]), node_type(sub.nodes[node])) if node in sub else ""

    properties = root.get("properties") or {}

    if not properties:
        return ""

    name = sorted(properties)[0]

    if "endpoints" in root:
        value = _edge_value(sub, *root["endpoints"], name)
    else:
        node = root.get("id")
        value = sub.nodes[node].get(name) if node in sub else None

    return "" if value is None else _value_text(value)

def _edge_value(graph, u, v, name):
    '''A property of the edge u--v; in a MultiGraph the one of the first parallel edge.'''
    if u not in graph or v not in graph or not graph.has_edge(u, v):
        return None

    data = graph.get_edge_data(u, v)
    attrs = data[next(iter(data))] if graph.is_multigraph() else data

    return attrs.get(name)

def _sites(instance, added, ref, sub):
    '''
    The edges of a bundle, one site each: the element's partner with expected
    and actual value ("»Auto« sollte 1 sein (gezeichnet n)"), an extra edge
    ("Kante zu »Kunde« zu viel") or a missing one.
    '''
    element = instance.get("sub_element")
    parts = []

    for op in instance.get("claims") or []:
        if "endpoints" not in op:
            continue

        a, b = op["endpoints"]
        partner = b if a == element else a if b == element else None
        who = (name_of(partner, added, ref, sub) if partner is not None
               else join_and([name_of(a, added, ref, sub), name_of(b, added, ref, sub)]))

        if op["op"] == "modify":
            parts.append(f"{who} sollte {_wanted(op)} sein (gezeichnet {_actual(op, sub) or 'nichts'})")
        elif op["op"] == "remove":
            parts.append(f"Kante zu {who} zu viel")
        else:
            parts.append(f"Kante zu {who} fehlt")

    return join_and(parts)

def _value_text(value):
    '''A value as text; a tuple (cardinality) without its empty positions.'''
    if isinstance(value, (list, tuple)):
        return "/".join(str(v) for v in value if v not in ("", None)) or "leer"

    return str(value)

def _consequences_text(consequences, added, ref, sub):
    '''" -- damit auch Beziehung »hat« und zwei Kanten", or empty.'''
    if not consequences:
        return ""

    # Sorted, not in op order: that order depends on the IDs, and the same
    # submission with different IDs would otherwise be listed the other way
    # round. The edges come last anyway.
    names = sorted(headword_of(op["id"], added, ref, sub)
                   for op in consequences if "endpoints" not in op)
    edges = sum(1 for op in consequences if "endpoints" in op)

    if edges == 1:
        names.append("eine Kante")
    elif edges > 1:
        names.append(f"{number_word(edges)} Kanten")

    return " -- damit auch " + join_and(names)

def _by_type(element, graph):
    '''The labels of the instance nodes per type -- for ref_<type> and sub_<type>.'''
    nodes = element if isinstance(element, (list, tuple)) else [element]
    grouped = {}

    for node in nodes:
        if isinstance(node, str) and node in graph:
            grouped.setdefault(node_type(graph.nodes[node]), []).append(
                f"»{node_label(graph.nodes[node]) or node}«")

    return grouped
