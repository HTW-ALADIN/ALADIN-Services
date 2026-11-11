'''
The error catalog: notations/<NOTATION>/<name>.fehlerkatalog.json.

One file, one reader. It has three blocks (the keys are the notation file's
own vocabulary and stay as they are):

    klassen     the error classes of the notation -- read by
                -> src/report/catalog
    ordnungen   per property the values from the narrowest to the widest
                rank, e.g. cardinality 1 before n = m. This gives a bundle of
                similar edge ops its direction
                (-> src/report/catalog/classify.py)
    bewertung   what holds for the whole course; what a single class costs
                is with the class itself under "punkte"

A notation without a catalog returns empty or None everywhere -- then
src/report/catalog classifies nothing, but the run goes on. The catalog is
a reading of the diff, not a precondition for it.

How a scoring entry is read:

    "bewertung" (scoring, at the top of the file)
        max         the reachable points, per task (null: unknown)
        vorbehalt   "voll" (full): instances that rest on an assumption count
                    like certain ones; "keiner" (none): they do not count, only
                    the follow-up question remains. No "half" -- that would be
                    a weight.
    "punkte" (points, per class)
        abzug       deduction in points, an integer from 0
        modus       "je_set" (once, no matter how many instances) or
                    "je_instanz" (times the number of instances)
        deckel      only with je_instanz: the cap, never more than this

A class without "punkte" is reported and costs nothing. Whether a
transformation is allowed is NOT stated here but in the transformation
declaration (-> src/notation/transformations.py, "allowed"): an allowed
transformation is not an error and therefore never costs anything.

load_catalog() returns all three as one Catalog (below): the classes as a
list, with .orders and .scoring on it. The scoring is a dict that no longer
knows about the file: {"vorbehalt", "max", "klassen": {catalog ID: punkte}}.
It is read by -> src/report/catalog/points.py.
'''

from . import files

#: The allowed values.
MODES = ("je_set", "je_instanz")
RESERVATIONS = ("voll", "keiner")

#: The fields under "punkte".
REQUIRED_KEYS = {"abzug", "modus"}
OPTIONAL_KEYS = {"deckel"}


@files.cached
def load_catalog_data(name):
    '''
    The whole catalog file of the notation as a dict: "klassen" (the
    entries), "bewertung" and, where present, "ordnungen". An empty dict
    without the file.
    '''
    return files.read(name, "catalog", optional=True) or {}


class Catalog(list):
    '''
    The error catalog of a notation -- one file, one thing.

    The classes ARE the list: whoever iterates the catalog gets the entries.
    What else is in the same file hangs next to it instead of needing a
    second loader:

        orders    the orders ("ordnungen") -- empty if the notation names
                  none; then src/report/catalog bundles nothing
        scoring   what an error costs ("bewertung" at the top, "punkte" per
                  class) -- None if the catalog knows no points

    An empty catalog is allowed: then src/report/catalog classifies nothing,
    but the run goes on.
    '''

    def __init__(self, classes=(), orders=None, scoring=None):
        super().__init__(classes)
        self.orders = orders or {}
        self.scoring = scoring


@files.cached
def load_catalog(name):
    '''The error catalog of the notation: classes, orders and scoring.'''
    data = load_catalog_data(name)

    return Catalog(data.get("klassen", []), data.get("ordnungen", {}), _scoring(name, data))


def _scoring(name, data):
    '''
    The scoring from the catalog file, checked -- or None if the catalog
    knows no points.
    '''
    classes = data.get("klassen", [])

    if "bewertung" not in data and not any("punkte" in entry for entry in classes):
        return None

    scoring = dict(data.get("bewertung") or {})
    scoring["klassen"] = {entry["id"]: entry["punkte"] for entry in classes if "punkte" in entry}
    _check(name, scoring)

    return scoring


def _check(name, scoring):
    '''
    Every value must be readable. A typo in the file thus shows up at
    program start.
    '''
    where = f"{name}{files.SUFFIXES['catalog']}"

    if scoring.get("vorbehalt", "voll") not in RESERVATIONS:
        raise ValueError(f"{where}: bewertung.vorbehalt must be one of {list(RESERVATIONS)}")

    if not isinstance(scoring.get("max", {}), dict):
        raise ValueError(f"{where}: bewertung.max is a dict {{task: points}}")

    for task, points in scoring.get("max", {}).items():
        if points is not None and (not isinstance(points, int) or points < 0):
            raise ValueError(f"{where}: bewertung.max.{task}: points are an integer from 0 or null")

    for class_id, entry in scoring["klassen"].items():
        here = f"{where}: {class_id}.punkte"
        fields = set(entry) if isinstance(entry, dict) else set()

        if not REQUIRED_KEYS <= fields or not fields <= REQUIRED_KEYS | OPTIONAL_KEYS:
            raise ValueError(f"{here}: expected the fields {sorted(REQUIRED_KEYS)} "
                             f"(plus optionally {sorted(OPTIONAL_KEYS)}), found {sorted(fields)}")

        if not isinstance(entry["abzug"], int) or entry["abzug"] < 0:
            raise ValueError(f"{here}: abzug is an integer from 0")

        if entry["modus"] not in MODES:
            raise ValueError(f"{here}: modus must be one of {list(MODES)}")

        if "deckel" in entry and entry["modus"] != "je_instanz":
            raise ValueError(f"{here}: deckel only exists with je_instanz")

        if "deckel" in entry and (not isinstance(entry["deckel"], int) or entry["deckel"] < 0):
            raise ValueError(f"{here}: deckel is an integer from 0")
