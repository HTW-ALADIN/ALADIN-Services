"""Singleton caching for loaded models (SBERT, gensim, CrossEncoder).

Ensures models are loaded once and reused across requests.
"""

from typing import Any

_sbert_models: dict[str, Any] = {}
_gensim_models: dict[str, Any] = {}
_cross_encoder_models: dict[str, Any] = {}


def get_sbert_model(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """Load or retrieve a cached SentenceTransformer model."""
    if model_name not in _sbert_models:
        from sentence_transformers import SentenceTransformer

        _sbert_models[model_name] = SentenceTransformer(model_name)
    return _sbert_models[model_name]


def get_gensim_model(model_name: str = "glove-wiki-gigaword-50") -> Any:
    """Load or retrieve a cached gensim KeyedVectors model."""
    if model_name not in _gensim_models:
        import gensim.downloader as api

        _gensim_models[model_name] = api.load(model_name)
    return _gensim_models[model_name]


def get_cross_encoder_model(model_name: str = "cross-encoder/stsb-roberta-base") -> Any:
    """Load or retrieve a cached CrossEncoder model."""
    if model_name not in _cross_encoder_models:
        from sentence_transformers import CrossEncoder

        _cross_encoder_models[model_name] = CrossEncoder(model_name)
    return _cross_encoder_models[model_name]


def clear_all():
    """Clear all cached models (useful for testing)."""
    _sbert_models.clear()
    _gensim_models.clear()
    _cross_encoder_models.clear()
