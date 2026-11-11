'''The shared configuration of the semantics. **All numbers live here.**'''
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ..normalization import PROFILES
from .stages import RESOURCE_NAMES, STAGES, check_stages

_LIST_SPLIT = re.compile(r"[|;,\s]+")

class RelationWeights(BaseModel):
    '''What a relation is worth as a score.'''

    model_config = {"extra": "forbid"}

    synonym: float = Field(1.00, ge=0.0, le=1.0)
    hypernym: float = Field(0.85, ge=0.0, le=1.0)
    hyponym: float = Field(0.85, ge=0.0, le=1.0)
    related: float = Field(0.50, ge=0.0, le=1.0)

    def weight_for(self, relation: str) -> float:
        '''The score of a relation. Unknown relation -> 0.0.'''
        return float(getattr(self, relation, 0.0))


class ResourceSpec(BaseModel):
    '''Where a knowledge base lives and which version it has.'''

    model_config = {"extra": "forbid"}

    path: Optional[str] = Field(
        default=None,
        description=("Local path, for the wordnet the data directory. "
                     "None = $SEMANTICS_WN_DATA (-> resources.py: locate_dir)."),
    )
    version: Optional[str] = Field(
        default=None, description="Expected version; checked against the file.",
    )


class SemanticConfig(BaseModel):
    '''What is compared semantically, and how.'''

    model_config = {"extra": "forbid"}

    enabled: bool = Field(
        default=True,
        description="Semantics on/off as a whole. Off == empty stage list.",
    )
    stages: list[str] = Field(
        default_factory=list,
        description=(
            "Methods in the desired order. Set in -> config.py "
            "(SEMANTIC_STAGES); a string with '|', ';', ',' or spaces works too. "
            "An empty list (the default) switches semantics off. "
            f"Known: {', '.join(sorted(STAGES))}."
        ),
    )
    input_profile: str = Field(
        default="whitespace",
        description=(
            "Normalization profile that runs BEFORE the lookup. A wordnet "
            "knows neither 'Kunden-Nr.' nor 'KUNDE ' -- without preprocessing "
            "the lookup simply fails. Default 'whitespace': spelling and "
            "editor line breaks gone, word boundaries and umlauts kept, "
            "because both matter for the lookup."
        ),
    )
    thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Per stage; whatever is missing here comes from the stage default.",
    )
    relation_weights: RelationWeights = Field(default_factory=RelationWeights)
    max_taxonomy_depth: int = Field(
        default=4, ge=0,
        description="Largest allowed number of edges in the broader graph.",
    )
    score_decimals: int = Field(
        default=6, ge=0, le=12,
        description=(
            "Rounding BEFORE every comparison against threshold and margin. "
            "Without it, byte-identical output is no longer guaranteed as soon "
            "as someone changes the machine (determinism)."
        ),
    )
    resources: dict[str, ResourceSpec] = Field(
        default_factory=dict,
        description=f"Per resource. Known: {', '.join(RESOURCE_NAMES)}.",
    )

    # ------------------------------------------------------------------ #

    @field_validator("stages", mode="before")
    @classmethod
    def _split_stages(cls, v: Any) -> Any:
        """Allow a string as a list -- config.py is edited by hand."""
        if isinstance(v, str):
            return [s for s in _LIST_SPLIT.split(v.strip()) if s]
        return v

    @field_validator("stages", mode="after")
    @classmethod
    def _known_stages(cls, v: list[str]) -> list[str]:
        """An unknown or duplicate stage fails loudly -- no silent degradation."""
        check_stages(v)
        return v

    @field_validator("input_profile", mode="after")
    @classmethod
    def _known_profile(cls, v: str) -> str:
        '''The profile must exist.'''
        if v not in PROFILES:
            raise ValueError(
                f"Unknown normalization profile {v!r}. "
                f"Known: {', '.join(sorted(PROFILES))}."
            )
        return v

    @field_validator("thresholds", mode="after")
    @classmethod
    def _known_threshold_keys(cls, v: dict[str, float]) -> dict[str, float]:
        """Thresholds only for known stages, and only within [0, 1]."""
        unknown = sorted(set(v) - set(STAGES))
        if unknown:
            raise ValueError(
                f"thresholds names unknown stage(s) {unknown}. "
                f"Known: {', '.join(sorted(STAGES))}."
            )
        outside = sorted(k for k, value in v.items() if not 0.0 <= value <= 1.0)
        if outside:
            raise ValueError(f"thresholds outside [0, 1]: {outside}.")
        return v

    @field_validator("resources", mode="after")
    @classmethod
    def _known_resource_keys(cls, v: dict[str, ResourceSpec]) -> dict[str, ResourceSpec]:
        '''Resource settings only for names that a stage also names.'''
        unknown = sorted(set(v) - set(RESOURCE_NAMES))
        if unknown:
            raise ValueError(
                f"resources names unknown resource(s) {unknown}. "
                f"Known: {', '.join(RESOURCE_NAMES)}."
            )
        return v

    # ------------------------------------------------------------------ #

    @property
    def active_stages(self) -> tuple[str, ...]:
        """The stages actually running -- empty if switched off."""
        return tuple(self.stages) if self.enabled else ()
