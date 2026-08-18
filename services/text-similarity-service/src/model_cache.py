"""Singleton caching for loaded models (SBERT, gensim, CrossEncoder)."""

import os
import threading
from collections.abc import Callable
from typing import Any

# ─── Large-download cost gate ─────────────────────────────────────────────────
#
# Runtime model downloads above this threshold (in MB) require an explicit
# opt-in BEFORE the first download — they must never be triggered silently.
# Below the threshold (e.g. glove ~200 MB) downloads run automatically.
# Sizes not in the known table are resolved via the gensim downloader metadata
# so an arbitrary ``params.model_name`` (e.g. a multi-GB model) still gates on
# its real size before any download is triggered.
LARGE_DOWNLOAD_THRESHOLD_MB = 500

# Known gensim-data download sizes (MB) for models above the threshold. The
# known-size table is a fast path; models not listed here are resolved via the
# gensim downloader metadata (see ``_gensim_info_size_mb``).
_GENSIM_LARGE_MODELS_MB = {
    "fasttext-wiki-news-subwords-300": 2048,
    "conceptnet-numberbatch-17-06-300": 1229,
}

# Cache of resolved gensim download sizes (MB) by model name, so the metadata
# lookup happens at most once per model.
_GENSIM_INFO_SIZES_MB: dict[str, int] = {}

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

    Models are gated if they exceed the threshold, whether listed in the
    known-size table or resolved from the gensim downloader metadata. Names the
    metadata cannot resolve are treated as 0 MB — that is not a bypass, since a
    model gensim cannot locate cannot be downloaded at all.
    """
    size_mb = _resolve_download_size_mb(model_name)
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


def _resolve_download_size_mb(model_name: str) -> int:
    """Return the expected download size (MB) for a model.

    Known gensim-data resources are cached in ``_GENSIM_LARGE_MODELS_MB`` (fast
    path). Any other name (e.g. an explicit ``params.model_name`` such as
    ``word2vec-google-news-300``) is resolved against the gensim downloader
    metadata to get its real ``filesize``. Unlocatable names resolve to 0 MB —
    that is not a bypass, because a model gensim cannot locate cannot be
    downloaded at all and ``api.load`` fails on its own.
    """
    known = _GENSIM_LARGE_MODELS_MB.get(model_name)
    if known is not None:
        return known
    return _gensim_info_size_mb(model_name)


def _gensim_info_size_mb(model_name: str) -> int:
    """Look up a model's download size (MB) via gensim's downloader metadata (cached)."""
    cached = _GENSIM_INFO_SIZES_MB.get(model_name)
    if cached is not None:
        return cached
    size_mb = 0
    try:
        import gensim.downloader as api

        meta = api.info(name=model_name)
        size_bytes = meta.get("filesize", 0)
        size_mb = int(round(size_bytes / (1024 * 1024))) if isinstance(size_bytes, (int, float)) else 0
    except Exception:  # noqa: BLE001  # unknown/unavailable metadata -> treat as unresolvable
        size_mb = 0
    _GENSIM_INFO_SIZES_MB[model_name] = size_mb
    return size_mb


_models: dict[str, Any] = {}
_models_lock = threading.Lock()


def _get(key: str, factory: Callable[[], Any]) -> Any:
    """Return the cached value for ``key``, loading it once via ``factory``.

    A module-level lock guards the check-then-set so two concurrent requests
    cannot both invoke ``factory()`` (each triggering a multi-GB model download)
    under a multi-worker or threaded deployment.
    """
    with _models_lock:
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


def ensure_wordnet() -> None:
    """Ensure the small NLTK WordNet corpora are available; download on first use.

    WordNet-backed measures (wordnet_similarity, synonym/antonym/hypernym/
    hyponym) read these ~12 MB corpora. Like HuggingFace/gensim resources they
    are downloaded on demand, never bundled into the image. Well under the
    large-download gate, so no opt-in is needed.
    """
    import nltk

    for resource in ("wordnet", "wordnet_ic"):
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True, raise_on_error=True)
        # NLTK >= 3.10 downloads corpora as a packed .zip; force-extract it if
        # the plain directory still isn't resolvable (see tests/conftest.py).
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            _extract_nltk_zip(resource)


def _extract_nltk_zip(resource: str) -> None:
    """Extract ``corpora/<resource>.zip`` into its parent so NLTK can resolve the dir."""
    import zipfile
    from pathlib import Path

    import nltk

    for corpora_dir in [Path(p) / "corpora" for p in nltk.data.path if (Path(p) / "corpora").is_dir()]:
        zip_path = corpora_dir / f"{resource}.zip"
        if zip_path.is_file():
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(corpora_dir)


ODENET_ID = "odenet:1.4"


def clear_all() -> None:
    """Clear all cached models (useful for testing)."""
    with _models_lock:
        _models.clear()
