'''Backend ``wordnet`` -- synsets, taxonomy and Wu-Palmer via ``wn``.'''
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import taxonomy
from ..verdict import (DIRECTION_REF_TO_SUB, DIRECTION_SUB_TO_REF,
                       DIRECTION_SYM, REASON_DEPTH_EXCEEDED,
                       REASON_NO_RELATION, REASON_OOV, REASON_SYNSET_OVERLAP,
                       REASON_TAXONOMY_PATH, REASON_WU_PALMER,
                       RELATION_HYPERNYM, RELATION_HYPONYM, RELATION_SYNONYM,
                       Verdict, no_verdict)
from ..wn_adapter import WordNetResource
from ._base import ScoredBackend

#: Order in which allowed relations are checked: stronger evidence first, so
#: the result does not depend on the order of checking.
_RELATION_ORDER: tuple[str, ...] = (
    RELATION_SYNONYM, RELATION_HYPERNYM, RELATION_HYPONYM,
)


@dataclass(frozen=True)
class WordNetBackend(ScoredBackend):
    '''One method on exactly one opened wordnet.'''

    resource: WordNetResource

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _base_evidence(self, ref_term: str, sub_term: str) -> dict:
        '''What every piece of evidence of this backend carries.'''
        return {
            "source": self.resource.specifier,
            "fingerprint": self.resource.fingerprint,
            "left": ref_term,
            "right": sub_term,
        }

    def _sense_evidence(self, ref_term: str, sub_term: str,
                        ref_syns: tuple[str, ...], sub_syns: tuple[str, ...]) -> dict:
        '''Base evidence plus the number of senses checked.'''
        evidence = self._base_evidence(ref_term, sub_term)
        evidence["ref_senses"] = len(ref_syns)
        evidence["sub_senses"] = len(sub_syns)
        return evidence

    # ------------------------------------------------------------------ #
    # The predicate
    # ------------------------------------------------------------------ #

    def relate(self, ref_term: str, sub_term: str) -> Verdict:
        '''How are the two labels related -- and how strongly?'''
        ref_syns = self.resource.synsets_for(ref_term)
        sub_syns = self.resource.synsets_for(sub_term)

        missing = [side for side, syns in (("ref", ref_syns), ("sub", sub_syns))
                   if not syns]
        if missing:
            evidence = self._sense_evidence(ref_term, sub_term, ref_syns, sub_syns)
            evidence["missing"] = missing
            return no_verdict(self.stage.name, REASON_OOV,
                              evidence_kind=self.stage.evidence_kind,
                              evidence=evidence)

        if self.stage.is_score_stage:
            return self._wu_palmer(ref_term, sub_term, ref_syns, sub_syns)
        return self._discrete(ref_term, sub_term, ref_syns, sub_syns)

    # ------------------------------------------------------------------ #

    def _discrete(self, ref_term: str, sub_term: str,
                  ref_syns: tuple[str, ...], sub_syns: tuple[str, ...]) -> Verdict:
        """Synonym and hypernym stages: the wordnet names a relation, not a measure."""
        allowed = [r for r in _RELATION_ORDER if r in self.stage.relations]

        for relation in allowed:
            if relation == RELATION_SYNONYM:
                shared = sorted(set(ref_syns) & set(sub_syns))
                if shared:
                        # Two equal labels drop out here by themselves: they
                        # resolve to the same set of synsets.
                    evidence = self._sense_evidence(ref_term, sub_term, ref_syns, sub_syns)
                    evidence["left_synset"] = shared[0]
                    evidence["right_synset"] = shared[0]
                    evidence["synsets"] = shared
                    return self._verdict(
                        relation=RELATION_SYNONYM, direction=DIRECTION_SYM,
                        reason=REASON_SYNSET_OVERLAP, evidence=evidence,
                    )
                continue

            found = self._taxonomy_hit(ref_syns, sub_syns, relation,
                                          max_depth=self.cfg.max_taxonomy_depth)
            if found is not None:
                path, direction, left, right = found
                evidence = self._sense_evidence(ref_term, sub_term, ref_syns, sub_syns)
                evidence["left_synset"] = left
                evidence["right_synset"] = right
                evidence["path"] = list(path)
                evidence["depth"] = len(path) - 1
                return self._verdict(
                    relation=relation, direction=direction,
                    reason=REASON_TAXONOMY_PATH, evidence=evidence,
                )

        return self._negative(ref_term, sub_term, ref_syns, sub_syns, allowed)

    def _wu_palmer(self, ref_term: str, sub_term: str,
                   ref_syns: tuple[str, ...], sub_syns: tuple[str, ...]) -> Verdict:
        '''Wu-Palmer stage: the taxonomy gives a measure, not a relation.'''
        best: Optional[tuple[float, str, str, str, int]] = None
        for r in ref_syns:                       # both already sorted by ID
            for s in sub_syns:                   # -- see synsets_for
                hit = taxonomy.wu_palmer(r, s, self.resource.broader,
                                             max_depth=self.cfg.max_taxonomy_depth)
                if hit is None:
                    continue
                value, subsumer, depth = hit
                rounded = self._round(value)
                # Strictly greater: on a tie the one seen first stays, and
                # because of the sorted iteration that is exactly the
                # lexicographically smallest pair (ref_id, sub_id).
                if best is None or rounded > best[0]:
                    best = (rounded, r, s, subsumer, depth)

        if best is None:
            return self._negative(ref_term, sub_term, ref_syns, sub_syns,
                                  (RELATION_HYPERNYM,))

        rounded, left, right, subsumer, depth = best
        evidence = self._sense_evidence(ref_term, sub_term, ref_syns, sub_syns)
        evidence["left_synset"] = left
        evidence["right_synset"] = right
        evidence["subsumer"] = subsumer
        evidence["depth"] = depth
        # ``rounded`` is already rounded -- ``_score_verdict`` rounds once
        # more, which is idempotent. Going through the shared place is still
        # right: the step from value to relation exists only once, otherwise a
        # value method would not be comparable with the others.
        return self._score_verdict(score=rounded, reason=REASON_WU_PALMER,
                                   evidence=evidence)

    # ------------------------------------------------------------------ #

    def _taxonomy_hit(self, ref_syns: tuple[str, ...], sub_syns: tuple[str, ...],
                      relation: str, *, max_depth: Optional[int]):
        '''
        The **shortest** ascent over all pairs of senses.

                Returns ``(path, direction, ref_synset, sub_synset)`` or ``None``.
        '''
        if relation == RELATION_HYPERNYM:
            direction = DIRECTION_SUB_TO_REF
        elif relation == RELATION_HYPONYM:
            direction = DIRECTION_REF_TO_SUB
        else:
            return None

        best = None
        for r in ref_syns:
            for s in sub_syns:
                if r == s:
                    # A synset is not a hypernym of itself. Otherwise a hyper
                    # stage would report a hypernymy for two equal labels, i.e.
                    # "named too generally", where simply the same word stands.
                    # The same decision as in ``taxonomy.directed_path``.
                    continue
                lowers, uppers = (r, s) if relation == RELATION_HYPERNYM else (s, r)
                path = taxonomy.directed_path(lowers, uppers, self.resource.broader,
                                              max_depth=max_depth)
                if path is None:
                    continue
                if best is None or len(path) < len(best[0]):
                    best = (path, direction, r, s)
        return best

    def _negative(self, ref_term: str, sub_term: str,
                  ref_syns: tuple[str, ...], sub_syns: tuple[str, ...],
                  allowed) -> Verdict:
        '''No hit -- but which kind of "no hit"?'''
        evidence = self._sense_evidence(ref_term, sub_term, ref_syns, sub_syns)

        taxonomic = [r for r in allowed
                       if r in (RELATION_HYPERNYM, RELATION_HYPONYM)]
        if self.stage.is_score_stage:
            taxonomic = [RELATION_HYPERNYM, RELATION_HYPONYM]

        for relation in taxonomic:
            found = self._taxonomy_hit(ref_syns, sub_syns, relation, max_depth=None)
            if found is not None:
                path, _direction, left, right = found
                evidence["left_synset"] = left
                evidence["right_synset"] = right
                evidence["path"] = list(path)
                evidence["depth"] = len(path) - 1
                evidence["max_taxonomy_depth"] = self.cfg.max_taxonomy_depth
                return no_verdict(self.stage.name, REASON_DEPTH_EXCEEDED,
                                  evidence_kind=self.stage.evidence_kind,
                                  evidence=evidence)

        return no_verdict(self.stage.name, REASON_NO_RELATION,
                          evidence_kind=self.stage.evidence_kind,
                          evidence=evidence)
