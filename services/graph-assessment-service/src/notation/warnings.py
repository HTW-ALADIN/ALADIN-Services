'''
What stands out about a notation without making it unusable.

Only one file is required, <name>.notation.json; if it is missing or broken,
the run ends while loading. Everything else is optional
(-> src/notation/files.py), and "optional" means "silent" here: without a
catalog the comparison runs through and just names no error class.

Two cases are allowed but almost always a mistake. They are listed here so
they show up once at start instead of showing as an empty table:

    no catalog        the diff is built but not classified --
                      no classes, no templates, no points
    no node types     the notation cannot accept anything: every node is
                      "unknown_type_or_value", every edge "edge_not_allowed"

Reported, not prevented: a notation under construction may be both.
The lines are printed by -> src/terminal_output (user-facing, German).

(The module has the same name as the stdlib module but does not hide it:
Python imports absolutely, so "import warnings" next door still gives the
stdlib.)
'''

from . import files
from .catalog import load_catalog
from .notation import load_notation


def notation_warnings(name):
    '''What stands out about the notation, as finished sentences -- empty is good.'''
    found = []

    if not load_notation(name).node_types:
        found.append(
            f"die Notation {name} deklariert keine Knotentypen: "
            f"jeder Knoten gilt als Verstoss, jede Kante auch")

    if not load_catalog(name):
        found.append(
            f"kein Fehlerkatalog ({name}{files.SUFFIXES['catalog']} fehlt oder nennt keine "
            f"Klassen): der Befund wird nicht klassifiziert, keine Punkte")

    return found
