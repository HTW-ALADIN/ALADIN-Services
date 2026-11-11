'''
The notation held against a diagram.

Next door the notation is read (one file, one module). Here it is applied:
to a concrete graph, as src/loading built it.

    properties.py  which values of a node or an edge count -- with default
                   and mapped to the equivalence group
    units.py       the units: references, owners, adornments, and splitting
                   a diagram into units

This is the layer src/mapping, src/transform and src/report keep asking. It
knows no node type by name -- the ERD knowledge is in notations/ERD/.
'''

from .properties import (canonical, edge_props, edge_props_raw, node_label, node_props,
                         node_props_raw, node_type, normalized)
from .units import (NO_REFERENCE, NOTATION_UNITS, TWO_CLAIMS, Decomposition, Unit, Units,
                    adornment_types, claims, claims_exclusively, decompose, owner_of,
                    references, skeleton, subgraph, unit_neighbours)

__all__ = [
    "Decomposition",
    "NOTATION_UNITS",
    "NO_REFERENCE",
    "TWO_CLAIMS",
    "Unit",
    "Units",
    "adornment_types",
    "canonical",
    "claims",
    "claims_exclusively",
    "decompose",
    "edge_props",
    "edge_props_raw",
    "node_label",
    "node_props",
    "node_props_raw",
    "node_type",
    "normalized",
    "owner_of",
    "references",
    "skeleton",
    "subgraph",
    "unit_neighbours",
]
