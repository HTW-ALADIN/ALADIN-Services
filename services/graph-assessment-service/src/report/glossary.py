'''
How students name what is in the reference solution.

After every run the mapping knows that "Auto" is called "Fahrzeuge" in this
submission and through which stage that came out (Mapping.source). Here this
is read off, collected and given back to the student.

    observe           reads a mapping -- pairs and open questions
    open_questions    the uncertain pairs as a table, then the open questions
    update_glossary   label list and questions on disk, across runs

The list (glossary/<task>.json, config.GLOSSARY_PATH) is written and never
read back: feeding the open cases of the assessed submissions back into a
knowledge base would tune the system on the very data it is judged by. It is
raw material for curating label lists by hand.

Every pair gets the label verdict (label_kind, -> src/mapping/labels/kind.py),
no matter which filter found it. "Uncertain" is what the name alone does not
support (UNCERTAIN_KINDS) -- plus the nodes that stayed ambiguous. And if not
a single name fits, probably something else was modelled.

The questions and the table are user-facing and stay German.
'''

import json
from datetime import date

from src.notation.diagram import node_label, node_type
from src.mapping.labels import NAMED_KINDS, UNCERTAIN_KINDS, label_kind
from .wording import TYPE_NAMES

#: The question when not a single name fits. Two causes are possible: the
#: wrong task was worked on, or everything was named meaninglessly
#: ("E1", "B5").
NO_NAME_FITS = ("Kein einziger Bezeichner passt zur Musterlösung -- ist es die "
                "richtige Aufgabe? Und falls ja: sind die Elemente "
                "wiedererkennbar benannt?")

#: The heading above the pairing table. It states what was paired and does
#: not judge -- the question is asked via the line marker "?"
#: (-> src/terminal_output.py).
TABLE_HEAD = "So wurden die Bezeichner einander zugeordnet:"

#: The column headers of the table, in this order.
COLUMNS = ("Knotentyp", "Reference", "Submission", "Mapping")

#: What the pairing rests on: the label verdict (-> src/mapping/labels/kind.py)
#: as the word in the "Mapping" column. What the name itself does not support
#: is in brackets -- there the structure alone decided.
MAPPING_WORDS = {
    "synonym": "gleiche Bedeutung",
    "compound": "gleicher Wortkern",
    "different": "(nur Struktur)",
}

#: The note written into the file itself -- so nobody has to look it up in
#: the source code.
FILE_NOTE = ("Collected automatically during runs, not curated. "
             "Never read back by the program.")


def observe(ref, sub, mapping):
    '''
    What this mapping says about labels -- (pairs, unresolved).

    pairs       per paired node: both labels, their kind and the mapping source
    unresolved  per ambiguous node: the reference label and the labels of
                the candidates
    '''
    pairs = []

    for r, s in mapping.pairs.items():
        ref_label = node_label(ref.nodes[r])
        sub_label = node_label(sub.nodes[s])

        pairs.append({
            "type": node_type(ref.nodes[r]),
            "reference": ref_label,
            "submission": sub_label,
            "kind": label_kind(ref_label, sub_label),
            "source": mapping.source.get(r, ""),
        })

    unresolved = [
        {
            "type": node_type(ref.nodes[entry["ref"]]),
            "reference": node_label(ref.nodes[entry["ref"]]),
            "candidates": sorted(node_label(sub.nodes[s])
                                 for s in entry["candidates"]),
        }
        for entry in mapping.ambiguous
    ]

    return pairs, unresolved


def open_questions(pairs, unresolved):
    '''
    The uncertain pairings -- a list of lines.

    First the special case: if not a single name fits, there is the one
    question about the task. Then the table of the pairs the name does not
    support, then what stayed ambiguous.
    '''
    lines = []

    # Also when nothing at all could be paired (pairs empty, but open cases
    # present) -- that is the clearer case, not the more harmless one.
    if (pairs or unresolved) and not any(entry["kind"] in NAMED_KINDS for entry in pairs):
        lines.append(NO_NAME_FITS)

    lines += _pair_table([entry for entry in pairs
                          if entry["kind"] in UNCERTAIN_KINDS])
    lines += [_ambiguity_question(entry) for entry in unresolved]

    return lines


def _pair_table(entries):
    '''
    The pairs the name does not support, as a table -- heading, column
    headers, one line per pair. Without a pair it is left out entirely.

    The last column says what the pairing rests on (MAPPING_WORDS): the stage
    of the cascade at which the two names came together -- or
    "(nur Struktur)" (structure only) if none applied.
    '''
    if not entries:
        return []

    rows = [(TYPE_NAMES.get(entry["type"], entry["type"] or "Knoten"),
             entry["reference"], entry["submission"],
             MAPPING_WORDS.get(entry["kind"], entry["kind"]))
            for entry in entries]
    widths = [max(len(str(cell)) for cell in column)
              for column in zip(COLUMNS, *rows)]

    return [TABLE_HEAD] + [_row(cells, widths) for cells in [COLUMNS] + rows]


def _row(cells, widths):
    '''A table line: indented, two spaces between the columns.'''
    return "  " + "  ".join(str(cell).ljust(width)
                            for cell, width in zip(cells, widths)).rstrip()


def _ambiguity_question(entry):
    '''
    An ambiguous node as a question.

    With exactly one candidate "which one is meant" would be wrong, so the
    sentence asks differently in that case.
    '''
    headword = _headword(entry["type"], entry["reference"])
    names = [f"»{name}«" for name in entry["candidates"]]

    if len(names) < 2:
        return f"{headword} blieb ohne Zuordnung -- kommt {names[0]} in Frage?"

    return f"Zu {headword} passten mehrere: {', '.join(names)} -- welches ist gemeint?"


def _headword(type_name, label):
    '''How a node is addressed: "Entität »Auto«" -- as in the sentences.'''
    return f"{TYPE_NAMES.get(type_name, type_name or 'Knoten')} »{label}«"


def update_glossary(path, task, observations):
    '''
    Update the label list and the questions -- {set_name: (pairs, unresolved)}
    in, two files out:

        <task>.json               per reference label all names students used
                                  for it, with verdict (label_kind) and
                                  origin -- the label list
        <task>_questions.json     the questions from open_questions, per set

    The sets of this run are first removed from the old files and then
    written anew. Otherwise an entry would remain that the current run no
    longer produces.
    '''
    questions_path = path.with_name(f"{path.stem}_questions.json")

    pairs = _without_sets(_flat_pairs(_load(path).get("labels", [])),
                          set(observations))
    questions = {name: lines
                 for name, lines in _load(questions_path).get("questions", {}).items()
                 if name not in observations}

    for set_name, (new_pairs, new_unresolved) in observations.items():
        for entry in new_pairs:
            _record(pairs, ("type", "reference", "submission", "kind"),
                    entry, set_name, entry["source"])

        lines = open_questions(new_pairs, new_unresolved)

        if lines:
            questions[set_name] = lines

    meta = {"task": task, "updated": date.today().isoformat(), "note": FILE_NOTE}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "meta": meta,
        "labels": _grouped(pairs),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    questions_path.write_text(json.dumps({
        "meta": meta,
        "questions": {name: questions[name] for name in sorted(questions)},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _flat_pairs(groups):
    '''The groups of the file back as flat pairs -- to merge with the run.'''
    return [{"type": group["type"], "reference": group["reference"],
             "submission": variant["label"], "kind": variant["kind"],
             "sets": variant["sets"]}
            for group in groups for variant in group["variants"]]


def _grouped(pairs):
    '''
    The pairs as a list per reference label: under it all names students
    used, the most frequent first.
    '''
    groups = []

    for entry in _sorted_entries(pairs, "submission"):
        key = (entry["type"], entry["reference"])

        if not groups or (groups[-1]["type"], groups[-1]["reference"]) != key:
            groups.append({"type": entry["type"], "reference": entry["reference"],
                           "variants": []})

        groups[-1]["variants"].append({"label": entry["submission"],
                                       "kind": entry["kind"],
                                       "count": entry["count"],
                                       "sets": entry["sets"]})

    for group in groups:
        group["variants"].sort(key=lambda v: (-v["count"], v["label"], v["kind"]))

    return groups


def _load(path):
    '''What is already there. If the file does not exist yet, it is empty.'''
    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def _without_sets(entries, current_sets):
    '''
    The existing entries without the sets that are about to be rewritten.

    An entry that occurs in no set afterwards is dropped entirely.
    '''
    kept = []

    for entry in entries:
        sets = {name: sources for name, sources in entry["sets"].items()
                if name not in current_sets}

        if sets:
            kept.append({**entry, "sets": sets})

    return kept


def _record(entries, fields, observation, set_name, source):
    '''
    Add an observation -- to the existing entry or as a new one.

    Two observations are equal if they agree in all "fields". Every
    occurrence is recorded on its own, even a repeated one.
    '''
    key = tuple(str(observation[field]) for field in fields)
    entry = next((e for e in entries
                  if tuple(str(e[field]) for field in fields) == key), None)

    if entry is None:
        entry = {field: observation[field] for field in fields}
        entry["sets"] = {}
        entries.append(entry)

    entry["sets"].setdefault(set_name, []).append(source)


def _sorted_entries(entries, second_field):
    '''The entries in a fixed order, with "count" in front.'''
    ordered = sorted(entries,
                     key=lambda e: (e["type"], e["reference"], str(e[second_field])))
    out = []

    for entry in ordered:
        without_sets = {field: value for field, value in entry.items() if field != "sets"}
        sets = {name: entry["sets"][name] for name in sorted(entry["sets"])}
        out.append({**without_sets,
                    "count": sum(len(sources) for sources in sets.values()),
                    "sets": sets})

    return out
