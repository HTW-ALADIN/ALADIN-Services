'''
Terminal output of a run.

Three blocks: the settings at start, the result per input and the summary
over all of them. Controlled by the PRINT_ switches in config.py.

The printed text is user-facing and stays German.
'''

from src import config
from src.notation import notation_warnings


def show_warnings():
    '''
    What stands out about the notation (-> src/notation/warnings.py), one line each.

    Independent of PRINT_INFO: a notation without a catalog or without node
    types still runs, but delivers something other than expected -- that
    should be visible even if the info block is off. If nothing stands out,
    nothing is printed.
    '''
    messages = notation_warnings(config.NOTATION)

    for message in messages:
        print(f"  ! {message}")

    if messages:
        print()


def show_info(notation):
    '''Prints the run settings if config.PRINT_INFO is on.'''
    if not config.PRINT_INFO:
        return

    # A single file takes precedence (-> config.SUBMISSION_FILE, start.py).
    if config.SUBMISSION_FILE:
        sets_info = f"eine Datei ({config.rel_path(config.SUBMISSION_FILE)})"
    elif config.RUN_ALL_SETS:
        sets_info = "Alle Sets"
    else:
        sets_info = f"Default Set ({config.DEFAULT_SET})"

    print(f"Daten:          {config.rel_path(config.TASK_DIR)}")
    print(f"Aufgabe:        {config.TASK}")
    print(f"Sets:           {sets_info}")
    print(f"Reference:      {config.rel_path(config.REFERENCE_PATH)}")
    print(f"Notation:       {notation.name} ({notation.graph_class})")
    print()



def show_result(result):
    '''
    Prints the result of a single input.

    A rejected submission gets one line with its class and, as feedback, the
    sentence for it -- nothing was compared.

    Line prefixes:
      -  notation violations (src/loading/validate.py)
      *  deviations from the reference (src/report/sentences.py)
      =  the deduction for them (src/report/catalog/points.py)
      ?  follow-up questions to the student (src/report/glossary.py)

    The last three are the feedback and depend on config.PRINT_FEEDBACK.
    '''
    if not result.loaded:
        # The rejection has a class (-> src/report/catalog.classify_rejection);
        # without a catalog the line stays as it was.
        class_label = "".join(f" ({_named(i)})" for i in getattr(result, "classes", ())[:1])

        print(f"  [{result.name}] ABGEWIESEN{class_label}: {result.rejection}")

        if config.PRINT_FEEDBACK:
            for line in getattr(result, "sentences", ()):
                print(f"           * {line}")

        return

    notation = ("notationskonform" if result.conforms
                else f"{len(result.violations)} Befund(e)")

    print(f"  [{result.name}] OK ({_graph_size(result.graph)}), "
          f"{notation}{_comparison_suffix(result)}")

    # 1. Notation violations (-> src/loading/validate.py: rule, text, affected)
    for violation in result.violations:
        print(f"           - {violation['text']}")

    # 2. The feedback: the deviations as sentences, the deduction, the follow-up questions
    if config.PRINT_FEEDBACK:
        for line in result.sentences:
            print(f"           * {line}")

        if getattr(result, "points", None) is not None:
            print(f"           = {points_line(result.points)}")

        for line in result.open_questions:
            print(f"           ? {line}")


def points_line(points):
    '''
    The deduction for one submission in one line:

        Abzug 9 von 30 Punkten: FK-5.1 Primary Key nicht gekennzeichnet 6, FK-3.1 Attribut fehlt 3
        kein Abzug (30 Punkte); zugelassen: FK-6.3 Attribut statt Relationship

    Externally a class is shown with its code from the catalog.
    '''
    rows = [row for row in points["deductions"] if row["deduction"]]
    maximum = points.get("max")

    if rows:
        text = f"Abzug {points['total']}" + (f" von {maximum} Punkten" if maximum else " Punkte")
        text += ": " + ", ".join(f"{_named(row)} {row['deduction']}" for row in rows)
    else:
        text = "kein Abzug" + (f" ({maximum} Punkte)" if maximum else "")

    free = [_named(row) for row in points["deductions"] if not row["scored"]]

    if free:
        text += "; ohne Abzug gemeldet: " + ", ".join(free)

    if points.get("accepted"):
        text += "; zugelassen: " + ", ".join(_named(row) for row in points["accepted"])

    return text


def _named(row):
    '''Code and name of a class; without a code only the name.'''
    return " ".join(part for part in (row.get("code"), row["name"]) if part)


def show_report(results):
    '''
    Prints the summary: accepted, notation-conforming and isomorphic
    submissions.

    For a single input nothing is printed here: "1 of 1" three times says
    nothing the result line above has not already said.
    '''
    results = list(results)

    if len(results) < 2:
        return

    loaded = [e for e in results if e.loaded]
    conforming = [e for e in loaded if e.conforms]
    compared = [e for e in loaded if e.compared]

    print()
    print(f"{len(loaded)} von {len(results)} Submissions eingelesen, "
          f"{len(results) - len(loaded)} abgewiesen")
    print(f"{len(conforming)} von {len(loaded)} Submissions notationskonform")

    if compared:
        isomorphic = [e for e in compared if e.isomorphic]
        print(f"{len(isomorphic)} von {len(compared)} Submissions isomorph zur Reference")

    print()


def _comparison_suffix(result):
    '''
    Formats the outcome of the reference comparison as an addition to the
    result line: either "isomorphic" or the number of deviations (including
    ambiguities).
    '''
    if not result.compared:
        return ""

    if result.isomorphic:
        return ", isomorph zur Reference"

    open_count = len(result.mapping.ambiguous) if result.mapping else 0
    assumed = sum(1 for op in result.deviations
                  if isinstance(op, dict) and "assumed" in op)
    suffix = f", {len(result.deviations)} Abweichung(en)"

    if assumed:
        suffix += f", davon {assumed} auf Annahmen"

    return suffix + (f" ({open_count} Knoten mehrdeutig)" if open_count else "")


def _graph_size(graph):
    '''The number of nodes and edges, for the result line.'''
    return f"{graph.number_of_nodes()} Knoten, {graph.number_of_edges()} Kanten"
