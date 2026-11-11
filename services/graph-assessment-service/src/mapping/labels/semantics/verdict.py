'''The one result type -- symbolic and numeric in the same shape.'''
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Relations
# --------------------------------------------------------------------------- #

RELATION_SYNONYM = "synonym"
RELATION_HYPERNYM = "hypernym"
RELATION_HYPONYM = "hyponym"
RELATION_RELATED = "related"
RELATION_NONE = "none"

#: All relations a backend may report. ``none`` is the statement "no
#: relation" and therefore a result, not an error state.
RELATIONS: tuple[str, ...] = (
    RELATION_SYNONYM,
    RELATION_HYPERNYM,
    RELATION_HYPONYM,
    RELATION_RELATED,
    RELATION_NONE,
)

#: The relations a stage can allow via ``StageSpec.relations``.
#: ``none`` is not in here -- one does not allow "no relation".
SELECTABLE_RELATIONS: tuple[str, ...] = (
    RELATION_SYNONYM,
    RELATION_HYPERNYM,
    RELATION_HYPONYM,
    RELATION_RELATED,
)

# --------------------------------------------------------------------------- #
# Direction
# --------------------------------------------------------------------------- #

#: The submission is more general than the reference ("Fahrzeug" instead of "PKW").
DIRECTION_SUB_TO_REF = "sub->ref"
#: The submission is more specific than the reference.
DIRECTION_REF_TO_SUB = "ref->sub"
#: Symmetric -- synonymy and every cosine measure.
DIRECTION_SYM = "sym"
DIRECTION_NONE = "none"

DIRECTIONS: tuple[str, ...] = (
    DIRECTION_SUB_TO_REF,
    DIRECTION_REF_TO_SUB,
    DIRECTION_SYM,
    DIRECTION_NONE,
)

# --------------------------------------------------------------------------- #
# Kind of evidence
# --------------------------------------------------------------------------- #

#: The evidence names a synset or taxonomy path -- traceable to a rule, so
#: every verdict can be explained.
EVIDENCE_SYMBOLIC = "symbolic"
#: The evidence names a number. Good for comparing, not as a basis for
#: grading -- every verdict must stay traceable.
EVIDENCE_NUMERIC = "numeric"

EVIDENCE_KINDS: tuple[str, ...] = (EVIDENCE_SYMBOLIC, EVIDENCE_NUMERIC)

# --------------------------------------------------------------------------- #
# reason tags
# --------------------------------------------------------------------------- #

REASON_SYNSET_OVERLAP = "synset-overlap"      # shared synset in the resource
REASON_TAXONOMY_PATH = "taxonomy-path"        # connected via hypernyms/hyponyms
REASON_WU_PALMER = "wu-palmer"                # computed via the taxonomy
REASON_BELOW_THRESHOLD = "below-threshold"    # value computed, below the threshold
REASON_DEPTH_EXCEEDED = "depth-exceeded"      # connection beyond max_taxonomy_depth

#: Kept apart from ``no-relation``, because the distinction measures the
#: **coverage** of the resource and not its calibration: a method with 60 %
#: ``oov`` does not have the wrong thresholds but the wrong vocabulary.
#: Throwing both into one tag would erase exactly this finding.
REASON_OOV = "oov"                            # at least one label unknown

REASON_NO_RELATION = "no-relation"            # both found, no relation

#: The complete set. A backend that returns a tag outside this list has broken
#: the contract.
REASONS: tuple[str, ...] = (
    REASON_SYNSET_OVERLAP,
    REASON_TAXONOMY_PATH,
    REASON_WU_PALMER,
    REASON_BELOW_THRESHOLD,
    REASON_DEPTH_EXCEEDED,
    REASON_OOV,
    REASON_NO_RELATION,
)


# --------------------------------------------------------------------------- #
# The result type
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Verdict:
    '''What a method says about **one** pair of labels.'''

    #: ``score >= threshold of the stage``. The decision belongs to the
    #: config, not to the method -- no backend is ever "sure".
    matched: bool
    #: [0, 1], already rounded to ``score_decimals``. The rounding happens in
    #: the backend, **before** the comparison against threshold and margin;
    #: otherwise byte-identical output is no longer guaranteed as soon as
    #: someone changes the machine.
    score: float
    relation: str
    direction: str
    #: Which stage said it.
    stage: str
    evidence_kind: str
    #: The evidence. Always with ``source`` and ``fingerprint``, so that a
    #: finding is worth something in an assessment context at all.
    evidence: dict
    reason: str

def no_verdict(stage: str, reason: str, *, evidence_kind: str = EVIDENCE_SYMBOLIC,
               evidence: dict | None = None) -> Verdict:
    '''The negative result in one line -- ``oov``, ``no-relation``, ...'''
    return Verdict(
        matched=False,
        score=0.0,
        relation=RELATION_NONE,
        direction=DIRECTION_NONE,
        stage=stage,
        evidence_kind=evidence_kind,
        evidence=dict(evidence or {}),
        reason=reason,
    )
