'''Semantic pairing of labels -- a plain text library, running on the wordnet in normal operation.'''
from __future__ import annotations

from . import compound
from .backends import BACKENDS, Backend, build as build_backend
from .config import RelationWeights, ResourceSpec, SemanticConfig
from .resources import (MissingResourceError, ResourceError, load_resource,
                        load_wordnet, locate_dir)
from .stages import (RESOURCE_NAMES, STAGES, StageError, StageSpec,
                     UnavailableBackendError, UnknownStageError, check_stages,
                     resources_for, spec_for, threshold_for)
from .verdict import (DIRECTIONS, EVIDENCE_KINDS, REASONS, RELATIONS, Verdict,
                      no_verdict)
from .wn_adapter import WordNetError, WordNetResource

__all__ = [
    "BACKENDS",
    "DIRECTIONS",
    "EVIDENCE_KINDS",
    "REASONS",
    "RELATIONS",
    "RESOURCE_NAMES",
    "STAGES",
    "Backend",
    "MissingResourceError",
    "RelationWeights",
    "ResourceError",
    "ResourceSpec",
    "SemanticConfig",
    "StageError",
    "StageSpec",
    "UnavailableBackendError",
    "UnknownStageError",
    "Verdict",
    "WordNetError",
    "WordNetResource",
    "build_backend",
    "check_stages",
    "compound",
    "load_resource",
    "load_wordnet",
    "locate_dir",
    "no_verdict",
    "resources_for",
    "spec_for",
    "threshold_for",
]
