'''
The pairing reference <-> submission -- the eight steps, one file per step.

    build.py        build_mapping: the sequence. 0 the skeleton, 5 again, 8 the rest
    anchors.py      1  exact anchors (exact_pairs), 1b a unique attribute
                       says who its owner is, 6 softer anchors
    regions.py      2  the piece of the reference grows in the submission:
                       seed, growth, harvest
    groups.py       3  the regions turn into groups: who faces the same choice
                       -- and the same group turned around, as candidates per
                       reference node (read by 7)
    names.py        4  within a group the name decides (NAME_STAGES: exact,
                       label, semantics, compound) -- and at the end names the
                       structural pairs
    adornments.py   6b the attributes go to the partner of their owner
    interchange.py  7  assign what is interchangeable: several candidates, built alike
    mapping.py      8  the data contract: the Mapping that src/report/diff.py reads

    unique.py          not a step but the rule below them: what is unique in
                       both directions (asked in 1, 4 and 7)

    isomorphism/    the structure: signature, anchored probe, full isomorphism
    labels/         the names: do two labels say the same thing? (normalization,
                    wordnet, compound) -- asked in steps 1, 4 and 6

The rule of the package in one sentence: only what is unique gets paired.
No type changes: a node with the wrong type is a break here, not a pair --
that belongs to the transformations (-> src/transform).
'''

from .build import build_mapping
from .mapping import Mapping

__all__ = ["Mapping", "build_mapping"]
