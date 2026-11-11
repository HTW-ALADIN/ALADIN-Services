'''
The wordnet as data: where it lives and how it gets there.

    data/       the database of the library "wn" plus manifest (no code)
    fetch.py    the build step that creates data/  (python -m src.knowledge.wordnet)

The data is read by src/mapping/labels/semantics; only WHERE it lives and HOW
it is obtained is defined here. Both belong together and not into the
comparison: a run that fetches data along the way is not repeatable.

Three places carry the word "wordnet", and they mean different things:

    src/knowledge/wordnet/            here -- the data and how it is obtained
    semantics/wn_adapter.py           the view on the library "wn":
                                      open, look up
    semantics/backends/wordnet.py     the method that turns it into a
                                      verdict; its file name IS the registry
                                      key (BACKEND_WORDNET)

This package is not called "odenet" even though it fetches OdeNet:
--lexicon also takes another one (-> fetch.py), and then the name would be
wrong.

data/downloads/ holds 2.4 MB that nobody reads in normal operation: the raw
LMF file as "wn" stores it when fetching. It stays anyway. The manifest names
it (lmf_file) and holds the SHA-256 over it, and nobody recomputes the
fingerprint the run reports as evidence (-> semantics/resources.py,
_wn_fingerprint). This file is the only thing the evidence can be checked
against; without it the evidence points to nothing. It can be obtained again
with python -m src.knowledge.wordnet.
'''

import os
from pathlib import Path

#: The environment variable that overrides the path. The same one that
#: src/mapping/labels/semantics/resources.py reads -- one variable, one truth.
DATA_ENV = "SEMANTICS_WN_DATA"

#: Where the wordnet database lives. The library "wn" gets an EXPLICIT path
#: here and never none at all: without one it falls back to ~/.wn_data and
#: downloads from the network on first access. $SEMANTICS_WN_DATA wins.
DATA_DIR = Path(os.environ.get(DATA_ENV) or Path(__file__).resolve().parent / "data")

#: The full ID and not just "odenet". Whoever pins a version gets that one or
#: an error -- otherwise a run against the wrong version looks like a run
#: against the right one.
LEXICON = "odenet:1.4"

#: The manifest next to the database: SHA-256 over the LMF file, synset count,
#: version, license, date. semantics/resources.py expects the same name.
MANIFEST = "manifest.json"

__all__ = ["DATA_DIR", "DATA_ENV", "LEXICON", "MANIFEST"]
