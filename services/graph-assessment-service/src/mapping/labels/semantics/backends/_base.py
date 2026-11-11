'''
What every backend MUST do the same way -- and therefore lives here only once.

The base currently has one subclass (the wordnet, -> wordnet.py). It stays
because it pins down the two things no backend may decide on its own:
rounding happens BEFORE the comparison against the threshold
(score_decimals, for determinism), and below the threshold there is no
verdict.
'''
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import SemanticConfig
from ..stages import StageSpec
from ..verdict import (DIRECTION_SYM, REASON_BELOW_THRESHOLD, RELATION_NONE,
                       RELATION_RELATED, Verdict)


@dataclass(frozen=True)
class ScoredBackend:
    '''Stage, config and effective threshold -- the shared base.'''

    stage: StageSpec
    cfg: SemanticConfig
    threshold: float

    def _round(self, value: float) -> float:
        '''Round BEFORE every comparison against threshold and margin.'''
        return round(float(value), self.cfg.score_decimals)

    def _verdict(self, *, relation: str, direction: str, reason: str,
                 evidence: dict, score: Optional[float] = None) -> Verdict:
        '''Score from the weights, threshold from the config, tag from the finding.'''
        weight = (self.cfg.relation_weights.weight_for(relation)
                if score is None else score)
        rounded = self._round(weight)
        matched = rounded >= self.threshold
        return Verdict(
            matched=matched,
            score=rounded,
            relation=relation,
            direction=direction,
            stage=self.stage.name,
            evidence_kind=self.stage.evidence_kind,
            evidence=evidence,
            reason=reason if matched else REASON_BELOW_THRESHOLD,
        )

    def _score_verdict(self, *, score: float, reason: str,
                       evidence: dict) -> Verdict:
        '''The verdict of a **score stage** -- Wu-Palmer as well as cosine.'''
        rounded = self._round(score)
        matched = rounded >= self.threshold
        return Verdict(
            matched=matched,
            score=rounded,
            relation=RELATION_RELATED if matched else RELATION_NONE,
            direction=DIRECTION_SYM,
            stage=self.stage.name,
            evidence_kind=self.stage.evidence_kind,
            evidence=evidence,
            reason=reason if matched else REASON_BELOW_THRESHOLD,
        )
