'''
The deviations as sentences, unit by unit.

Not a step of its own but a renderer over the op list from
src/report/diff.py: it adds nothing and leaves nothing out. The ops of a
unit are bundled, so that "Attribut »Ort« fehlt an »Filiale«" is shown
instead of three unrelated lines.

What an op assumes, the sentence says too -- as certain as the pair it
rests on (src/report/diff.py, "assumed"):

    pair     "Annahme: »Name« ist Attribut »ID« -- falls nicht: ..."
    group    the choice among interchangeable candidates as ONE sentence: what
             is there, what is expected, how many are extra, and which ones
             probably

A "delete FIN" without that addition would be an instruction where there is
only a guess.

If describe() gets the catalog's class instances (-> src/report/catalog),
ONE sentence is said per instance with a template instead of the unit
sentences of its ops: a transformation with 22 ops is one line, "Entität
»Leiter« fehlt" names the consequences in a trailing clause. An instance
that no op hangs on at all -- notation finding and label verdict -- gets its
sentence first: it concerns the submission as a whole, not a place in the
op list. This second way lives next door (-> templates.py); this module only
decides when it applies. Without instances or without a template everything
stays as it was.

How a thing is called in a sentence -- type word, label, enumeration,
number word -- is in -> wording.py and holds for both ways.

The sentences are user-facing and stay German.
'''

from src.notation.diagram import claims_exclusively, node_label, node_type, references

from .templates import (Slots, choice_of, claimless_instances, instance_sentence,
                       told_instances)
from .wording import (TYPE_NAMES, headword_of, join_and, listing, name_of,
                       number_word, ref_name, type_of)


def describe(ops, ref, sub, instances=(), catalog=()):
    '''
    The op list as sentences, one unit after the other.

    Returns a list of lines in op order, the sentences without an op first.
    "instances" are the class instances of the same diff, "catalog" the
    entries with their templates: where both are given, ONE sentence per
    instance replaces the sentences of its ops (-> told_instances). Without
    them it stays with the unit sentences.
    '''
    # Newly added nodes are in neither graph: their ID was assigned by the
    # diff, type and label are in the op itself.
    added = {op["id"]: op for op in ops if op.get("op") == "add" and "id" in op}

    lines = []
    told = []     # the groups that already have their sentence (identity, not equality)
    seen = set()  # the pairs whose assumption has already been stated
    claimed_by = told_instances(instances, catalog)

    # Whatever hangs on no op comes first: the notation finding and the label
    # verdict object to the submission without changing anything in it -- so
    # there is no place in the op list their sentence would belong to
    # (-> templates.py, claimless_instances).
    lines += [instance_sentence(instance, template, added, ref, sub)
              for instance, template in claimless_instances(instances, catalog)]

    # Edge ownership follows the type the op list leaves behind -- the node is
    # named the way it stands, though. That is why the copy is made only here.
    for anchor, group in _grouped(ops, added, ref, _with_new_types(sub, ops)).items():
        # First the ops that an instance with a template claims: its sentence
        # stands where its first op stands, and only once.
        rest = []

        for op in group:
            found = claimed_by.get(id(op))

            if found is None:
                rest.append(op)
                continue

            instance, template = found

            if not any(instance is known for known in told):
                told.append(instance)
                lines.append(instance_sentence(instance, template, added, ref, sub))
                lines += _assumption_sentences(instance["claims"], seen, ref, sub)

        group = rest

        if not group:
            continue

        choice = choice_of(group)

        if choice is not None:
            # A node that is extra or missing within a visible choice:
            # not "is extra", but the whole choice -- once.
            if not any(choice is known for known in told):
                told.append(choice)
                lines.append(_choice_sentence(choice, added, ref, sub))

            continue

        if anchor is None:
            lines += [_unclaimed_sentence(op, added, ref, sub) for op in group]
        else:
            lines += _unit_sentences(anchor, group, added, ref, sub)

        lines += _assumption_sentences(group, seen, ref, sub)

    return lines


def describe_rejection(instances, catalog):
    '''
    The rejection as a sentence -- the template of its class, with {grund} filled.

    A separate path, because a rejected submission was never loaded: there
    are no ops describe() could tell and no graph an element could be named
    from. So only the placeholders that have a value without a graph are
    filled -- the rest renders empty (-> Slots).
    '''
    templates = {entry.get("id"): entry.get("feedback") or "" for entry in catalog}
    lines = []

    for instance in instances:
        template = templates.get(instance.get("class"))

        if not template:
            continue

        slots = Slots({"name": instance.get("name") or "",
                        "klasse": instance.get("class") or "",
                        "grund": instance.get("reason") or ""})
        lines.append(" ".join(template.format_map(slots).split()))

    return lines


def _named(nodes, added, ref, sub):
    '''
    The names of these nodes in a fixed order -- alphabetical.

    Otherwise the order of the node list in the file would count: the same
    submission, written down in a different order, would say "stehen »Name«
    und »Mail«" instead of "»Mail« und »Name«". What the enumeration says does
    not change -- only the order is fixed.
    '''
    return sorted(name_of(n, added, ref, sub) for n in nodes)


def _choice_sentence(choice, added, ref, sub):
    '''
    A choice among interchangeable candidates as one sentence.

        An »VermietVorgang« stehen die Attribute »FIN«, »KundenID«, »Mietbeginn«
        und »Rückgabdatum«; erwartet sind »DatBeginn« und »DatRueckgabe« --
        zwei davon sind zu viel (vermutlich »FIN« und »KundenID«)

    What is there is certain; which ones are meant is the guess -- and that
    is how the sentence puts it.
    '''
    refs, candidates, pairs = choice["refs"], choice["candidates"], choice["pairs"]

    if not pairs:
        # The case that stayed open: nothing was assigned. Then nothing is
        # proven about the candidates either -- they may have another type
        # and hang somewhere else (that is exactly what the group leaves
        # open, -> src/mapping/interchange.py). The sentence below claims
        # both, so this case gets its own. -> _open_case_sentence()
        return _open_case_sentence(refs, candidates, added, ref, sub)

    kept = set(pairs.values())
    surplus = [s for s in candidates if s not in kept]
    missing = [r for r in refs if r not in pairs]

    type_name = node_type(ref.nodes[refs[0]]) if refs[0] in ref else ""
    here = listing(type_name, _named(candidates, added, ref, sub))
    wanted = join_and(sorted(ref_name(r, ref) for r in refs))

    # Where the candidates hang -- they all hang at the same place (fingerprint).
    # The roles keep the notation's order, sorting happens within them.
    neighbours = [name
                  for role_neighbours in references(sub, candidates[0]).values()
                  for name in _named(role_neighbours, added, ref, sub)
                  ] if candidates[0] in sub else []

    if neighbours:
        preposition = "An" if type_name == "attribute" or len(neighbours) < 2 else "Zwischen"
        opening = f"{preposition} {join_and(neighbours)} {here}"
    else:
        opening = f"Es {here}"

    if surplus:
        count = number_word(len(surplus))
        verb = "ist" if len(surplus) == 1 else "sind"
        guess = join_and(_named(surplus, added, ref, sub))
        closing = f"{count} davon {verb} zu viel (vermutlich {guess})"
    else:
        count = number_word(len(missing))
        verb = "fehlt" if len(missing) == 1 else "fehlen"
        guess = join_and(sorted(ref_name(r, ref) for r in missing))
        closing = f"{count} {verb} (vermutlich {guess})"

    return f"{opening}; erwartet {'ist' if len(refs) == 1 else 'sind'} {wanted} -- {closing}"


def _open_case_sentence(refs, candidates, added, ref, sub):
    '''
    A case that stayed open, as one sentence.

        Zu Attribut »Datum« passten »Zeitpunkt« und »Zeitpunkt«, belegt ist
        keine Zuordnung -- so gelesen fehlt »Datum«, und die genannten sind
        zu viel

    Unlike an interchangeable group, nothing is proven here: neither that
    the candidates have the same type nor that they hang on the same node. So
    the sentence claims neither -- it names them and says how the op list
    reads them. What is meant is asked by src/report/glossary.py.
    '''
    wanted = join_and(sorted(ref_name(r, ref) for r in refs))
    headword = (f"{TYPE_NAMES.get(node_type(ref.nodes[refs[0]]), 'Knoten')} {wanted}"
                if refs[0] in ref else wanted)
    names = join_and(_named(candidates, added, ref, sub))

    if len(candidates) == 1:
        closing = f"so gelesen fehlt {wanted}, und {names} ist zu viel"
    else:
        closing = f"so gelesen fehlt {wanted}, und die genannten sind zu viel"

    verb = "passte" if len(candidates) == 1 else "passten"

    return f"Zu {headword} {verb} {names}, belegt ist keine Zuordnung -- {closing}"


def _assumption_sentences(group, seen, ref, sub):
    '''
    The assumptions behind the ops of a unit, once per pair.

        Annahme: »Name« ist Attribut »ID« -- falls nicht: Attribut »ID« fehlt
        und »Name« ist zu viel

    The second half is the other reading -- the one the student means if the
    name is taken seriously.
    '''
    lines = []

    for op in group:
        pair = op.get("assumed", {}).get("pair")

        if not pair or tuple(pair) in seen:
            continue

        seen.add(tuple(pair))
        r, s = pair
        headword = (f"{TYPE_NAMES.get(node_type(ref.nodes[r]), 'Knoten')} {ref_name(r, ref)}"
                    if r in ref else f"Knoten »{r}«")
        name = f"»{node_label(sub.nodes[s]) or s}«" if s in sub else f"»{s}«"

        lines.append(f"Annahme: {name} ist {headword} -- falls nicht: "
                     f"{headword} fehlt und {name} ist zu viel")

    return lines


def _with_new_types(sub, ops):
    '''
    The submission with the types the op list gives it.

    Only for the grouping: edge ownership should follow the corrected type.
    Without a type op it is the same submission as before, otherwise a copy.
    '''
    retyped = {op["id"]: op["type"] for op in ops
               if op.get("op") == "modify" and "type" in op and "id" in op}

    if not retyped:
        return sub

    copy = sub.copy()

    for node, type_name in retyped.items():
        copy.nodes[node]["type"] = type_name

    return copy


def _grouped(ops, added, ref, sub):
    '''Bundle the ops by unit -- anchor -> [ops], None for ownerless ones.'''
    # Which nodes the list itself adds or removes -- the fallback rule for
    # edges that no unit claims.
    node_ops = {}

    for op in ops:
        if "endpoints" not in op and op.get("op") in ("add", "remove"):
            node_ops.setdefault(op["op"], set()).add(op.get("id"))

    grouped = {}

    for op in ops:
        anchor = _anchor_of(op, added, ref, sub, node_ops)
        grouped.setdefault(anchor, []).append(op)

    return grouped


def _anchor_of(op, added, ref, sub, node_ops=None):
    '''
    Which unit does this op belong to?

    Node ops belong to their own node. Edge ops belong to the end that claims
    the edge. If neither or both claim it, it belongs to the end that the same
    list adds or removes -- an edge goes with its node. That is needed after a
    type change: an entity retyped to a relationship no longer claims the edge
    to a relationship. If that is undecided too, the edge has no owner (None).
    '''
    if "endpoints" not in op:
        return op.get("id")

    a, b = op["endpoints"]
    end_side = claims_exclusively(type_of(a, added, ref, sub), type_of(b, added, ref, sub))

    if end_side is not None:
        return a if end_side == "a" else b

    own = (node_ops or {}).get(op.get("op"), set())

    if (a in own) != (b in own):
        return a if a in own else b

    return None


def _unit_sentences(anchor, group, added, ref, sub):
    '''
    The sentences of a unit.

    If the whole unit is missing or extra, it is summed up in one sentence;
    everything else gets a line of its own.
    '''
    node_op = next((op for op in group if "endpoints" not in op), None)
    edges = [op for op in group if "endpoints" in op]
    kind = node_op.get("op") if node_op else None

    if kind in ("add", "remove"):
        neighbours = _named([_other_end(op, anchor)
                             for op in edges if op.get("op") == kind],
                            added, ref, sub)
        rest = [op for op in edges if op.get("op") != kind]

        # src/report/diff.py lists the edges of a removed node one by one --
        # except those to ambiguous candidates, which are off limits. If none
        # is in the list, the submission says what the node hung on; otherwise
        # this would say "Attribut »Name« ist zu viel" without saying where.
        if not neighbours and anchor in sub:
            neighbours = [name
                          for role_neighbours in references(sub, anchor).values()
                          for name in _named(role_neighbours, added, ref, sub)]

        return ([_whole_unit_sentence(kind, anchor, neighbours, added, ref, sub)]
                + [_edge_sentence(op, anchor, added, ref, sub) for op in rest])

    lines = []

    if kind == "modify":
        lines.append(f"{headword_of(anchor, added, ref, sub)}: "
                     f"{_correction(node_op)}")

    return lines + [_edge_sentence(op, anchor, added, ref, sub) for op in edges]


def _whole_unit_sentence(kind, anchor, neighbours, added, ref, sub):
    '''A unit that is missing entirely or extra entirely -- one sentence.'''
    headword = headword_of(anchor, added, ref, sub)

    if not neighbours:
        return f"{headword} fehlt" if kind == "add" else f"{headword} ist zu viel"

    type_name = type_of(anchor, added, ref, sub)
    # "zwischen" (between) needs two sides. If the diff names only one,
    # "an" (at) is the more honest preposition.
    preposition = "an" if type_name == "attribute" or len(neighbours) < 2 else "zwischen"
    place = f"{preposition} {join_and(neighbours)}"

    # The word order changes with the verb: "fehlt an X", but "an X ist zu viel".
    if kind == "add":
        return f"{headword} fehlt {place}"

    return f"{headword} {place} ist zu viel"


def _edge_sentence(op, anchor, added, ref, sub):
    '''An edge whose unit is otherwise in place.'''
    headword = headword_of(anchor, added, ref, sub)
    target = name_of(_other_end(op, anchor), added, ref, sub)
    kind = op.get("op")

    if kind == "add":
        return f"{headword} ist nicht mit {target} verbunden"

    if kind == "remove":
        return f"{headword} ist zusätzlich mit {target} verbunden"

    return f"{headword} zu {target}: {_value_corrections(op.get('properties', {}))}"


def _unclaimed_sentence(op, added, ref, sub):
    '''An edge without a unit -- it is named by its two ends.'''
    a, b = op["endpoints"]
    end_names = [name_of(a, added, ref, sub), name_of(b, added, ref, sub)]
    kind = op.get("op")

    # For "missing" and "extra" the edge says nothing about its sides -- so
    # the names may stand in a fixed order. For a correction they may NOT:
    # the cardinality is stored position by position relative to the ends
    # (-> src/notation/diagram/properties.py), and reversed, the sentence
    # would say the opposite.
    if kind in ("add", "remove"):
        ends = " und ".join(sorted(end_names))

        return (f"Kante zwischen {ends} fehlt" if kind == "add"
                else f"Kante zwischen {ends} ist zu viel")

    return (f"Kante zwischen {' und '.join(end_names)}: "
            f"{_value_corrections(op.get('properties', {}))}")


def _correction(op):
    '''What has to be corrected at an assigned node -- type and values.'''
    parts = []

    if "type" in op:
        type_name = op["type"]
        # "Typ sollte X sein" instead of "sollte ein X sein": the indefinite
        # article would be the only thing that needs an inflection table.
        parts.append(f"Typ sollte {TYPE_NAMES.get(type_name, type_name)} sein")

    values = _value_corrections(op.get("properties", {}))

    if values:
        parts.append(values)

    return ", ".join(parts)


def _value_corrections(properties):
    '''What should be at this place.'''
    return ", ".join(f"{name} sollte {value!r} sein"
                     for name, value in sorted(properties.items()))


def _other_end(op, anchor):
    '''The end of the edge that is not the anchor -- for a loop, the anchor itself.'''
    a, b = op["endpoints"]

    return b if a == anchor else a
