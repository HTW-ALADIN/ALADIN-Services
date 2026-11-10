"""Pluggable export-format registry.

Adding a new format is a single new module + one line in `FORMATS` below --
no changes needed anywhere else (search/dedup/graph logic is unaffected).
"""

from __future__ import annotations

from collections.abc import Callable

from core.paper import Paper

from . import bibtex, ris
from . import csv as csv_export
from . import json as json_export

ExportFn = Callable[[list[Paper]], bytes]

FORMATS: dict[str, ExportFn] = {
    "bibtex": bibtex.serialize,
    "ris": ris.serialize,
    "csv": csv_export.serialize,
    "json": json_export.serialize,
}


def export(papers: list[Paper], fmt: str) -> bytes:
    if fmt not in FORMATS:
        available = ", ".join(sorted(FORMATS))
        raise KeyError(f"Unknown export format '{fmt}'. Available formats: {available}")
    return FORMATS[fmt](papers)
