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


# ─── HuggingFace model allowlist (optional [model] extra) ────────────────────
#
# The [model] measures (sbert_cosine, semantic_search, cross_encoder, bertscore)
# load pre-trained weights from HuggingFace Hub at runtime. Their ``model_name`` /
# ``model_type`` params are free-form by default, which would let a caller ask
# the host to download an arbitrary multi-GB (or third-party) checkpoint
# server-side with no opt-in. To close that hole we only accept a short, curated
# list of well-known models. Names are matched WITHOUT the common HuggingFace
# org prefixes ("sentence-transformers/", "cross-encoder/", ...), so both
# "all-MiniLM-L6-v2" and "sentence-transformers/all-MiniLM-L6-v2" are accepted.
_ALLOWED_BASE_MODELS: dict[str, set[str]] = {
    "sbert_cosine": {
        "all-MiniLM-L6-v2",  # default; ~22.7M params / ~90 MB
        "all-mpnet-base-v2",  # heavier (~109M params) SBERT
        "paraphrase-multilingual-MiniLM-L12-v2",  # multilingual
    },
    "semantic_search": {
        "all-MiniLM-L6-v2",
        "all-mpnet-base-v2",
        "paraphrase-multilingual-MiniLM-L12-v2",
    },
    "cross_encoder": {
        "stsb-roberta-base",  # default cross-encoder
    },
    "bertscore": {
        "roberta-large",  # bert_score's default model_type for lang='en'
    },
}

# Measures that may NOT be freely overridden via params (no modeled name lookup
# exists): kept explicit so a typo in the mapping above fails loudly.
_KNOWN_HF_MEASURES = frozenset(_ALLOWED_BASE_MODELS.keys())


def _normalize_hf_name(model_name: str) -> str:
    """Return the org-prefix-stripped base name (last path segment)."""
    return model_name.split("/", 1)[-1].strip()


def require_allowed_model(measure: str, model_name: str | None) -> None:
    """Validate an HF ``model_name``/``model_type`` against the allowlist.

    ``model_name=None`` means the measure uses its built-in default (e.g.
    BERTScore deriving ``roberta-large`` for ``lang='en'``), which is already on
    the list. Raises ``ValueError`` (surfaced as HTTP 400) for anything else so
    no unvetted checkpoint can be pulled down server-side.
    """
    allowed = _ALLOWED_BASE_MODELS.get(measure)
    if allowed is None:
        raise ValueError(f"'{measure}' is not an HF model-backed measure; cannot allow-list it.")
    if model_name is None:
        return  # built-in default is curated by construction
    base = _normalize_hf_name(model_name)
    if base not in allowed:
        raise ValueError(f"model_name/model_type '{model_name}' is not on the allow-list for '{measure}'. Allowed: {sorted(allowed)}")


def allowlisted_model_names(measure: str) -> list[str]:
    """Expose the allowed base names for a measure (docs/debugging)."""
    return sorted(_ALLOWED_BASE_MODELS.get(measure, set()))


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

    A model whose data is ALREADY PRESENT in the gensim data dir (pre-cached on
    disk, e.g. baked into a container image) also passes: there is nothing to
    download, so the cost gate is not engaged.

    Models are gated if they exceed the threshold, whether listed in the
    known-size table or resolved from the gensim downloader metadata. Names the
    metadata cannot resolve are treated as 0 MB — that is not a bypass, since a
    model gensim cannot locate cannot be downloaded at all.
    """
    size_mb = _resolve_download_size_mb(model_name)
    if size_mb <= LARGE_DOWNLOAD_THRESHOLD_MB:
        return
    if f"gensim:{model_name}" in _models:
        return  # already downloaded/cached in RAM — nothing would be downloaded
    if _gensim_model_on_disk(model_name):
        return  # model data already present in the gensim data dir — no download
    params = params or {}
    opt_in = params.get("confirm_large_download") is True or os.environ.get(ALLOW_LARGE_MODEL_DOWNLOADS_ENV, "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not opt_in:
        raise LargeModelDownloadBlocked(model_name, size_mb)


def _gensim_model_on_disk(model_name: str) -> bool:
    """Whether the gensim model data already exists in the gensim data dir.

    ``gensim.downloader.api.load`` skips its download when ``<data_dir>/<name>``
    exists. Mirror that check so a model that was pre-cached into the data dir
    (e.g. baked into a container image at build time) is NOT flagged as a
    "large download" by the cost gate — the data is already there, nothing would
    be downloaded.
    """
    import gensim.downloader as api

    folder_dir = os.path.join(api.BASE_DIR, model_name)
    return os.path.isdir(folder_dir) and any(os.scandir(folder_dir))


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
    """Look up a model's download size (MB) via gensim's downloader metadata (cached).

    Three outcomes, so a transient failure can never let a large model slip
    past the cost gate:

    - **Known** name -> its real ``file_size`` (Bytes; the metadata field is
      ``file_size``, not ``filesize``).
    - **Unknown** name -> gensim raises ``ValueError("Incorrect model/corpus
      name")``; treated as ``0``. That is not a bypass, because a model gensim
      cannot locate cannot be downloaded at all (``api.load`` fails on its own).
    - **Metadata lookup fails** for any *other* reason (network error, malformed
      index, ...) -> return a value above the threshold. That is deliberately
      conservative: the gate must block something it cannot size, never pass it.
      Such failures are also NOT cached, so a later successful lookup is not
      masked by a transient error.
    """
    import gensim.downloader as api

    try:
        meta = api.info(name=model_name)
    except ValueError:
        # Deterministic "unknown model name" signal -> nothing to gate.
        _GENSIM_INFO_SIZES_MB[model_name] = 0
        return 0
    except Exception:  # noqa: BLE001  # transient lookup failure -> conservative block
        return LARGE_DOWNLOAD_THRESHOLD_MB + 1

    if isinstance(meta, dict):
        size_bytes = meta.get("file_size")
        if isinstance(size_bytes, (int, float)) and size_bytes > 0:
            size_mb = int(round(size_bytes / (1024 * 1024)))
        else:
            size_mb = 0  # known but unsized -> leave ungated (not quantifiable)
    else:
        size_mb = 0
    _GENSIM_INFO_SIZES_MB[model_name] = size_mb
    return size_mb


_models: dict[str, Any] = {}
# One lock PER cache key. The meta-lock guards only the lock dict itself (tiny,
# held for nanoseconds), NEVER the model-loading factory. This lets two requests
# that load *different* models proceed in parallel, while two requests loading
# the *same* model still serialize so a multi-GB download happens exactly once.
_models_locks: dict[str, threading.Lock] = {}
_models_locks_guard = threading.Lock()


def _get(key: str, factory: Callable[[], Any]) -> Any:
    """Return the cached value for ``key``, loading it once via ``factory``.

    Per-key locking: two concurrent requests for the *same* key cannot both run
    ``factory()`` (each triggering a multi-GB model download), but requests for
    *different* keys do not block each other — loading SBERT while a gensim
    model downloads is no longer serialized behind a single global lock.
    """
    with _models_locks_guard:
        lock = _models_locks.setdefault(key, threading.Lock())
    with lock:
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

# ─── Warm-start preload (analogous to the ConceptNet sidecar) ──────────────
#
# By default the service starts COLD: no model is loaded, so boot is fast
# (~1s) and idle RAM is tiny (~0.05 GB), but the FIRST request for a model
# pays the full load time (downloading is pre-cached in the hf image, so it's
# disk->RAM only, ~6-21s for a transformer).
#
# The set of models to warm at startup is BAKED IN at image build time via the
# ``HF_PRELOAD`` build-arg (stored as an ENV in the image):
#   off (default)  — nothing preloaded; a fresh container is fully lazy.
#   all            — warm every advertised HF model (the old
#                    ``HF_MODELS_PRELOAD=true`` behaviour): higher idle RAM,
#                    no first-request delay.
#   measure:model[,measure:model...] — PARTIAL lazy: only the selected models
#                    are warmed into RAM; every other advertised model stays
#                    lazy and loads on its first request.
# The legacy ``HF_MODELS_PRELOAD=true`` env is still honoured as a synonym for
# ``all`` so existing deployments keep working. This mirrors the list of HF
# models that the runtime catalog advertises (see the build-time pre-cache,
# __precache_hf.py) so exactly the models a warm process would otherwise
# lazily load are warm. It is a no-op in the base ``cpu`` profile (no [model]
# extra installed).
HF_PRELOAD_ENV = "HF_PRELOAD"
_LEGACY_PRELOAD_ENV = "HF_MODELS_PRELOAD"

_DFLT_PRELOAD_HF = (
    ("sbert_cosine", "all-MiniLM-L6-v2"),
    ("sbert_cosine", "all-mpnet-base-v2"),
    ("sbert_cosine", "paraphrase-multilingual-MiniLM-L12-v2"),
    ("cross_encoder", "cross-encoder/stsb-roberta-base"),
    ("bertscore", "roberta-large"),
)


def _normalize_measure(measure: str) -> str:
    """Map a measure name to the allowlist key it must be validated against.

    ``semantic_search`` reuses the ``sbert_cosine`` allowlist (same underlying
    SentenceTransformer models); everything else maps 1:1. An unknown measure
    returns itself, so it simply fails validation below instead.
    """
    return "sbert_cosine" if measure == "semantic_search" else measure


def _parse_preload_spec() -> list[tuple[str, str]]:
    """Resolve the ``HF_PRELOAD`` env into an ordered list of (measure, model).

    Accepts:
      unset/off/none/false            -> ``[]`` (fully lazy)
      all/true/1                      -> the whole ``_DFLT_PRELOAD_HF`` list
      a CSV of ``measure:model`` pairs -> only those selected models
    Unknown measures, models off the allowlist, or malformed entries are
    logged and skipped (never fatal — warm start must not break boot). The
    legacy ``HF_MODELS_PRELOAD=true`` env is treated as ``all``.
    """
    import logging
    import re

    logger = logging.getLogger(__name__)

    raw = os.environ.get(HF_PRELOAD_ENV, "").strip()
    if raw.lower() in ("", "off", "none", "false", "0"):
        if os.environ.get(_LEGACY_PRELOAD_ENV, "").lower() in ("1", "true", "yes"):
            return list(_DFLT_PRELOAD_HF)
        return []
    if raw.lower() in ("all", "true", "1"):
        return list(_DFLT_PRELOAD_HF)

    selected: list[tuple[str, str]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        match = re.match(r"^([^:/]+):(.+)$", entry)
        if not match:
            logger.warning("HF_PRELOAD: ignoring malformed entry %r (expected measure:model)", entry)
            continue
        measure, model = match.group(1).strip(), match.group(2).strip()
        allowed = _ALLOWED_BASE_MODELS.get(_normalize_measure(measure))
        if allowed is None:
            logger.warning("HF_PRELOAD: unknown measure %r; ignoring %r", measure, entry)
            continue
        base = _normalize_hf_name(model)
        if base not in allowed:
            logger.warning(
                "HF_PRELOAD: model %r not on the allow-list for measure %r; ignoring %r",
                model,
                measure,
                entry,
            )
            continue
        selected.append((measure, model))
    return selected


def warm_start() -> None:
    """Preload the selected HF models into the in-process cache at startup.

    The selection comes from the ``HF_PRELOAD`` env (baked in at build time) —
    ``off`` (default), ``all``, or a partial ``measure:model`` list. Returns
    without doing anything when the selection is empty, when the optional
    PyTorch stack is not installed, or when a model fails to load (a warm
    start must never prevent the app from booting — it just relaxes to lazy
    loading for that model). Logs each model as it is loaded so operators can
    observe the warm-up.
    """
    import logging

    logger = logging.getLogger(__name__)
    for measure, model_name in _parse_preload_spec():
        try:
            if measure == "sbert_cosine":
                get_sbert_model(model_name)
            elif measure == "cross_encoder":
                get_cross_encoder_model(model_name)
            elif measure == "bertscore":
                # BERTScore keeps roberta-large in its own module-level cache,
                # not via ``_get``, so warm it by wrapping a scorer (this loads
                # the checkpoint + tokenizer into the module-level singleton).
                from bert_score import BERTScorer

                BERTScorer(lang="en", model_type=model_name)
            logger.info("warm-start loaded %s(%s)", measure, model_name)
        except Exception:  # noqa: BLE001  # warm start must be non-fatal
            logger.warning("warm-start failed for %s(%s); models stay lazy", measure, model_name)


def is_warm() -> bool:
    """Whether the configured ``HF_PRELOAD`` profile warms any model (for /metrics).

    True when the baked-in profile is ``all`` or a non-empty partial list;
    False for ``off``. Note this reports the *configured* selection, not
    whether those models actually finished loading (see ``cache_summary``).
    """
    return bool(_parse_preload_spec())


def cache_summary() -> dict[str, Any]:
    """Return a snapshot of the in-memory model cache (for observability).

    Exposes which keys are loaded so an operator can see which models are
    resident (and, indirectly, RAM usage) without logging internals.
    """
    with _models_locks_guard:
        return {"keys": sorted(_models.keys()), "count": len(_models)}


def clear_all() -> None:
    """Clear all cached models (useful for testing)."""
    with _models_locks_guard:
        _models.clear()
        _models_locks.clear()
