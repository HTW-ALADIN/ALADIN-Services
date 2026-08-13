"""Singleton caching for loaded models (SBERT, gensim, CrossEncoder)."""

from collections.abc import Callable
from typing import Any

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


def clear_all() -> None:
    """Clear all cached models (useful for testing)."""
    _models.clear()
