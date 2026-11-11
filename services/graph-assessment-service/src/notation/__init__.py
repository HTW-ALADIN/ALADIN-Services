'''
Read the notation with everything that belongs to it (notation-agnostic).
What it describes lives in notations/<NOTATION>/, only how to read it lives
here.

One file of the notation, one module -- the tree here looks like the folder
there, and the entrance has exactly four loaders, one per file:

    notation.py          <name>.notation.json        load_notation() -> Notation
    file_format.py       <name>.austauschformat.json load_file_format()  (exchange format)
    catalog.py           <name>.fehlerkatalog.json   load_catalog() -> Catalog  (error catalog)
    transformations.py   <name>.umformungen.json     load_transforms()  (transformations)

The rest belongs to no single file and is therefore not a loader:

    files.py             which files exist, finding and reading them raw -- the
                         layer below the four loaders. It also explains why
                         every loader caches its notation (cached): a run asks
                         for the same file several times, it is read and
                         checked once
    warnings.py          what stands out about a notation without making it
                         unusable -- printed by -> src/terminal_output.py

    diagram/             the notation held against a diagram: which values
                         count (properties.py) and how a diagram splits into
                         units (units.py). The only subfolder, because it is the
                         only one that no longer reads but applies.

What is a block of its own in a file hangs on the thing the file returns --
it needs no second loader:

    notation.units    notation.rules
    catalog.orders    catalog.scoring

The files are found by the name of the notation (config.NOTATION), not by a
path. No module here knows a node type by name -- the ERD knowledge is in
the files.
'''

from .catalog import Catalog, load_catalog, load_catalog_data
from .file_format import load_file_format
from .notation import Notation, load_notation
from .transformations import load_transforms
from .warnings import notation_warnings

__all__ = [
    "Catalog",
    "Notation",
    "load_catalog",
    "load_catalog_data",
    "load_file_format",
    "load_notation",
    "load_transforms",
    "notation_warnings",
]
