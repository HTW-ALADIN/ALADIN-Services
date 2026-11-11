'''The stage registry -- one named method per line.'''
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .verdict import EVIDENCE_NUMERIC, EVIDENCE_SYMBOLIC, SELECTABLE_RELATIONS

# --------------------------------------------------------------------------- #
# Backends and resources -- as constants, so a typo in the table below fails
# at import and not only when a file is loaded.
# --------------------------------------------------------------------------- #

BACKEND_WORDNET = "wordnet"

#: Only the wordnet runs in normal operation (-> label_match.py: active_stages).
BACKEND_NAMES: tuple[str, ...] = (BACKEND_WORDNET,)

RESOURCE_ODENET = "odenet"

class StageError(ValueError):
    """A stage list is configured incorrectly."""


class UnknownStageError(StageError):
    """The requested stage name is not in the registry."""


class UnavailableBackendError(StageError):
    """The stage is known, but its backend is not built in this version."""


@dataclass(frozen=True)
class StageSpec:
    '''A method as the registry lists it.'''

    name: str
    backend: str
    resource: str
    relations: tuple[str, ...]
    threshold: float
    evidence_kind: str

    @property
    def is_score_stage(self) -> bool:
        """Does the backend return a value instead of a relation?"""
        return not self.relations


#: The registry of all methods: name -> StageSpec.
STAGES: dict[str, StageSpec] = {
    # -- synonymy via the synsets of a wordnet --------------------------- #
    #    (the default, and the only stage that runs in normal operation --
    #     -> label_match.py: active_stages, config.py: SEMANTIC_STAGES)
    "syn_wordnet": StageSpec(
        name="syn_wordnet", backend=BACKEND_WORDNET, resource=RESOURCE_ODENET,
        relations=("synonym",), threshold=1.0, evidence_kind=EVIDENCE_SYMBOLIC,
    ),
    # -- hypernyms/hyponyms via the taxonomy ------------------------------ #
    #    Built, but off: one correct pair (Auto/Fahrzeug) against three
    #    questionable ones (ID/Name).
    "hyper_wordnet": StageSpec(
        name="hyper_wordnet", backend=BACKEND_WORDNET, resource=RESOURCE_ODENET,
        relations=("hypernym", "hyponym"), threshold=0.85,
        evidence_kind=EVIDENCE_SYMBOLIC,
    ),
    # -- taxonomic similarity (Wu-Palmer) --------------------------------- #
    #    Off: the threshold 0.85 was tuned on the same data it was evaluated on.
    "wup_wordnet": StageSpec(
        name="wup_wordnet", backend=BACKEND_WORDNET, resource=RESOURCE_ODENET,
        relations=(), threshold=0.85, evidence_kind=EVIDENCE_SYMBOLIC,
    ),
}


#: All resource names any stage names -- derived, not copied. The config
#: checks ``resources`` keys against it, so a mistyped name fails instead of
#: having no effect.
RESOURCE_NAMES: tuple[str, ...] = tuple(sorted({s.resource for s in STAGES.values()}))


def _check_registration() -> None:
    '''Check at import that the table is consistent.'''
    problems: list[str] = []
    for key, spec in STAGES.items():
        if key != spec.name:
            problems.append(f"{key!r}: key and StageSpec.name ({spec.name!r}) differ")
        if spec.backend not in BACKEND_NAMES:
            problems.append(f"{key!r}: unknown backend {spec.backend!r}")
        if spec.evidence_kind not in (EVIDENCE_SYMBOLIC, EVIDENCE_NUMERIC):
            problems.append(f"{key!r}: unknown evidence kind {spec.evidence_kind!r}")
        if not 0.0 <= spec.threshold <= 1.0:
            problems.append(f"{key!r}: threshold {spec.threshold} is outside [0, 1]")
        unknown = [r for r in spec.relations if r not in SELECTABLE_RELATIONS]
        if unknown:
            problems.append(f"{key!r}: unknown relation(s) {unknown}")
    if problems:
        raise RuntimeError("stages: registry is not consistent. " + "; ".join(problems) + ".")


_check_registration()


def spec_for(stage: str) -> StageSpec:
    '''The ``StageSpec`` for a name.'''
    try:
        return STAGES[stage]
    except KeyError:
        raise UnknownStageError(
            f"Unknown stage {stage!r}. Known: {', '.join(sorted(STAGES))}."
        ) from None


def check_stages(stages: Iterable[str]) -> tuple[str, ...]:
    '''Check a stage list and return it as a tuple.'''
    seq = tuple(stages)
    for s in seq:
        spec_for(s)

    duplicate = sorted({s for s in seq if seq.count(s) > 1})
    if duplicate:
        raise StageError(
            f"Stage listed twice in {seq}: {duplicate}. When pairing, every stage "
            "runs on the rest of the previous one -- a second pass of the same "
            "stage finds nothing more."
        )
    return seq


def resources_for(stages: Iterable[str]) -> tuple[str, ...]:
    '''The resource names a stage list needs -- without duplicates.'''
    seen: dict[str, None] = {}
    for s in stages:
        seen.setdefault(spec_for(s).resource, None)
    return tuple(seen)


def threshold_for(stage: str, overrides: dict[str, float] | None = None) -> float:
    '''The effective threshold: config beats default.'''
    spec = spec_for(stage)
    if overrides and stage in overrides:
        return float(overrides[stage])
    return spec.threshold
