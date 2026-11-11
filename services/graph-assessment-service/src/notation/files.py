'''
Find the files of a notation and read them raw.

Which files exist is defined here and only here -- the table SUFFIXES below.
What is in them is interpreted by one module each next door; one file, one
module:

    <name>.notation.json         -> notation.py      (the notation itself, with
                                    the blocks "units" and "regeln" in it)
    <name>.austauschformat.json  -> file_format.py   (the format of a graph file)
    <name>.fehlerkatalog.json    -> catalog.py       (the error classes, their
                                    orders and what an error costs)
    <name>.umformungen.json      -> transformations.py

The notation file is required. Everything else may be missing: then the
notation does not know this kind of knowledge, and the run goes on without
it -- what stays silent then is reported by -> src/notation/warnings.py.

The transformations have a file of their own and are not in the notation
file, because they are not part of the notation: they say how to recognize
that two diagrams build the same thing differently, and carry the course's
verdict on it (allowed). JSON carries no justifications.

Files are found by the name of the notation, not by a path --
config.NOTATION names it.
'''

import json
from functools import lru_cache, wraps
from pathlib import Path

NOTATIONS_DIR = Path(__file__).resolve().parents[2] / "notations"

#: The files of a notation: which module reads them, and what they are called.
#: Whoever introduces a fifth file adds it here and nowhere else.
SUFFIXES = {
    "notation":        ".notation.json",
    "file_format":     ".austauschformat.json",
    "catalog":         ".fehlerkatalog.json",
    "transformations": ".umformungen.json",
}

#: The only required file -- without it the name is not a notation.
REQUIRED = "notation"


#: The cached loaders -- needed by tests that put something else under the
#: same name (-> cached, cache_clear_all).
_CACHED = []


def cached(loader):
    '''
    Cache a loader: read and check once per notation, not once per caller.

    A run asks for the same notation several times -- start.py, the three
    modules that read from it at import time (src/report/wording.py,
    src/report/catalog/classify.py, src/notation/diagram/units.py), and the
    notation warnings. Without the cache that would be the notation five
    times and the catalog three times, each time glob, JSON and check. Now
    once.

    The key is the name AND the directory: tests put something else into a
    tmp_path under the same name (-> NOTATIONS_DIR). Whoever additionally
    swaps the layer below (read, load_catalog_data) has to clear the cache.

    Caching is only allowed because nobody changes the return values:
    notation and catalog are read throughout the program and never written.
    '''
    inner = lru_cache(maxsize=None)(lambda name, directory: loader(name))

    @wraps(loader)
    def wrapper(name):
        return inner(name, NOTATIONS_DIR)

    wrapper.cache_clear = inner.cache_clear
    wrapper.cache_info = inner.cache_info
    _CACHED.append(wrapper)

    return wrapper


def cache_clear_all():
    '''Make all cached loaders forget (-> cached).'''
    for loader in _CACHED:
        loader.cache_clear()


def find(name, which, optional=False):
    '''
    The path of a notation file. Exactly one hit, otherwise an error.

    "optional" means: no hit is fine and returns None. Two hits stay an
    error even then -- then it is not decided which file applies.
    '''
    suffix = SUFFIXES[which]
    matches = sorted(NOTATIONS_DIR.glob(f"*/{name}{suffix}"))

    if optional and not matches:
        return None

    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one file {name}{suffix} under {NOTATIONS_DIR}, "
            f"found: {[str(p) for p in matches]}"
        )

    return matches[0]


def read(name, which, optional=False):
    '''
    A notation file as JSON -- or None if it may be missing and is missing.

    Before an optional file, the required file is searched for: that way an
    unknown notation shows up here and not silently as "just has no catalog".
    '''
    if optional and which != REQUIRED:
        find(name, REQUIRED)

    path = find(name, which, optional=optional)

    if path is None:
        return None

    return json.loads(path.read_text(encoding="utf-8"))
