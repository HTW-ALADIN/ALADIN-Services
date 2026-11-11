'''Backend registry -- what is actually built in this version.'''
from __future__ import annotations

from typing import Callable, Optional, Protocol

from ..config import SemanticConfig
from ..stages import (BACKEND_WORDNET, StageSpec, UnavailableBackendError,
                      spec_for, threshold_for)
from ..verdict import Verdict
from ..wn_adapter import WordNetResource
from ._base import ScoredBackend
from .wordnet import WordNetBackend


class Backend(Protocol):
    '''What a backend must be able to do: say something about **one** pair.'''

    def relate(self, ref_term: str, sub_term: str) -> Verdict: ...


#: Backend name -> factory. The factory gets the loaded resource, because
#: loading is file access and belongs to the caller (``resources.py``).
#:
#: ``wordnet`` is listed here even if the library ``wn`` is missing -- that is
#: reported by ``resources.load_wordnet`` as a missing resource. It is the
#: only backend (-> ../stages.py).
BACKENDS: dict[str, Callable[..., Backend]] = {
    BACKEND_WORDNET: WordNetBackend,
}


def build(stage: str, resource: WordNetResource, *,
          cfg: SemanticConfig, spec: Optional[StageSpec] = None) -> Backend:
    '''Build the backend of a stage on a resource that is already loaded.'''
    spec = spec or spec_for(stage)
    factory = BACKENDS.get(spec.backend)
    if factory is None:
        raise UnavailableBackendError(
            f"Stage {stage!r} needs the backend {spec.backend!r}, which is not "
            f"built in this version. Built: "
            f"{', '.join(sorted(BACKENDS))}."
        )
    return factory(
        stage=spec,
        resource=resource,
        cfg=cfg,
        threshold=threshold_for(stage, cfg.thresholds),
    )


__all__ = ["BACKENDS", "Backend", "ScoredBackend", "WordNetBackend", "build"]
