"""Singleton caching for loaded models (SBERT, gensim, CrossEncoder)."""

import os
from collections.abc import Callable
from typing import Any

# ─── Large-download cost gate ─────────────────────────────────────────────────
#
# Runtime model downloads above this threshold (in MB) require an explicit
# opt-in BEFORE the first download — they must never be triggered silently.
# Below the threshold (e.g. glove ~200 MB) downloads run automatically.
LARGE_DOWNLOAD_THRESHOLD_MB = 500

# Known gensim-data download sizes (MB) for models above the threshold. Only
# models listed here are gated; smaller models and the remote ConceptNet API
# (0 MB) need no opt-in.
_GENSIM_LARGE_MODELS_MB = {
    "fasttext-wiki-news-subwords-300": 2048,
    "conceptnet-numberbatch-17-06-300": 1229,
}

# Env var that unlocks large runtime downloads server-wide (default: false).
ALLOW_LARGE_MODEL_DOWNLOADS_ENV = "ALLOW_LARGE_MODEL_DOWNLOADS"


class LargeModelDownloadBlocked(Exception):
    """Raised when a >500 MB model download was requested without an opt-in."""

    def __init__(self, model_name: str, size_mb: int) -> None:
        super().__init__(
            f"Model '{model_name}' requires an ~{size_mb} MB runtime download "
            f"(above the {LARGE_DOWNLOAD_THRESHOLD_MB} MB cost threshold). Explicitly opt in with "
            f"params.confirm_large_download=true on this request, or set {ALLOW_LARGE_MODEL_DOWNLOADS_ENV}=true "
            f'server-side, then retry. See README "Cost threshold for runtime downloads".'
        )
        self.model_name = model_name
        self.size_mb = size_mb


def require_large_download_ok(model_name: str, params: dict[str, Any] | None = None) -> None:
    """Block a large model download unless the caller opted in — gate only BEFORE the first download.

    Already-cached models pass unconditionally (a second call runs normally);
    the gate exists purely to stop silent first-time downloads. Opt-in is either
    per-request (``params.confirm_large_download: true``) or server-wide
    (``ALLOW_LARGE_MODEL_DOWNLOADS=true``).
    """
    size_mb = _GENSIM_LARGE_MODELS_MB.get(model_name, 0)
    if size_mb <= LARGE_DOWNLOAD_THRESHOLD_MB:
        return
    if f"gensim:{model_name}" in _models:
        return  # already downloaded/cached — nothing would be downloaded
    params = params or {}
    opt_in = params.get("confirm_large_download") is True or os.environ.get(ALLOW_LARGE_MODEL_DOWNLOADS_ENV, "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not opt_in:
        raise LargeModelDownloadBlocked(model_name, size_mb)


_models: dict[str, Any] = {}


def _get(key: str, factory: Callable[[], Any]) -> Any:
    if key not in _models:
        _models[key] = factory()
    return _models[key]


def get_sbert_model(model_name: str = "all-MiniLM-L6-v2") -> Any:
    from sentence_transformers import SentenceTransformer

    return _get(f"sbert:{model_name}", lambda: SentenceTransformer(model_name))


def get_gensim_model(model_name: str = "glove-wiki-gigaword-50") -> Any:
    import gensim.downloader as api

    return _get(f"gensim:{model_name}", lambda: api.load(model_name))


def get_cross_encoder_model(model_name: str = "cross-encoder/stsb-roberta-base") -> Any:
    from sentence_transformers import CrossEncoder

    return _get(f"cross_encoder:{model_name}", lambda: CrossEncoder(model_name))


def get_odenet() -> Any:
    """Lazily load (and cache) the Open German WordNet via the ``wn`` library.

    Requires the optional ``de`` extra (``pip install -e '.[de]'``). The Odenet
    data itself is downloaded on first use and cached in the wn database (not
    bundled into the image).
    """
    import wn

    def factory() -> Any:
        if ODENET_ID not in {lex.id for lex in wn.lexicons()}:
            wn.download(ODENET_ID)
        return wn.Wordnet(ODENET_ID)

    return _get("odenet", factory)


ODENET_ID = "odenet:1.4"


def clear_all() -> None:
    """Clear all cached models (useful for testing)."""
    _models.clear()
