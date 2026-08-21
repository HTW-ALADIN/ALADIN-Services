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


# Information-content corpus for the IC-based WordNet similarity variants
# (res / jcn / lin). The caller must NOT supply the corpus itself over the wire —
# NLTK's IC structure uses integer synset-offset keys, which JSON always coerces
# to strings, so a JSON round-trip silently breaks the lookups. Instead the
# canonical IC corpus is loaded server-side (cached), and ``params.ic`` merely
# names which published ``wordnet_ic`` corpus file to use (default ``ic-brown.dat``).
_IC_CACHE: dict[str, Any] = {}
_DEFAULT_IC = "ic-brown.dat"


def get_wordnet_ic(corpus: str | None = None) -> Any:
    """Return a cached NLTK Information-Content corpus.

    ``corpus`` selects the published ``wordnet_ic`` file (e.g. ``ic-brown.dat``,
    ``ic-semcor.dat``, ``ic-shakespeare-wln.freq``). It is resolved server-side
    only; raw IC objects cannot be provided by clients (see module docstring).
    """
    ensure_wordnet()
    name = corpus or _DEFAULT_IC
    if name not in _IC_CACHE:
        from nltk.corpus import wordnet_ic

        _IC_CACHE[name] = wordnet_ic.ic(name)
    return _IC_CACHE[name]


ODENET_ID = "odenet:1.4"

# ─── HF preload: ONE switch for disk pre-cache AND RAM warm-start ──────────
#
# ``HF_PRELOAD`` is a single build-arg (baked into the image as ENV) that
# controls BOTH how many model weights land on the IMAGE DISK at build time and
# how many are warmed into RAM at container start:
#
#   off (default)   — MODE 1 = cold start. Nothing is pre-downloaded to the
#                     disk and nothing is warmed into RAM; every model is
#                     lazy-loaded (and downloaded, if absent) on its first
#                     request. Smallest image, no idle RAM.
#   all             — MODE 2 = warm start. Every advertised HF model is
#                     pre-downloaded to the image disk at build time AND loaded
#                     into RAM at startup: higher idle RAM, but the first
#                     request is served in milliseconds with no network.
#   measure:model[,measure:model...] — PARTIAL. Only the selected models are
#                     pre-downloaded to disk and warmed into RAM; everything
#                     else is not present at all (lazy download at runtime).
#
# The same selection drives the build-time disk pre-cache (__precache_hf.py)
# and the runtime RAM warm-start (warm_start), so "what runs warm" and "what is
# on disk" can never drift apart. The maps below are the single source of truth
# for both: each advertised model is keyed by measure and knows the loader
# strategy it needs. It is a no-op in the base ``cpu`` profile (no [model]
# extra installed).
HF_PRELOAD_ENV = "HF_PRELOAD"

# Every advertised HF model mapped to the loader it needs, as a nested dict so a
# partial list can be validated and executed directly.
_DFLT_PRELOAD_HF: dict[str, set[str]] = {
    "sbert_cosine": {
        "all-MiniLM-L6-v2",
        "all-mpnet-base-v2",
        "paraphrase-multilingual-MiniLM-L12-v2",
    },
    "cross_encoder": {
        "cross-encoder/stsb-roberta-base",
    },
    "bertscore": {
        "roberta-large",
    },
}


def _semantic_search_measures() -> set[str]:
    """The measure names that load a SentenceTransformer (SBERT-family)."""
    return {"sbert_cosine", "semantic_search"}


def _preload_entries(raw: str | None) -> list[tuple[str, str]]:
    """Parse a raw ``HF_PRELOAD`` value into an ordered list of (measure, model).

    Accepts ``off``/``none``/``false``/empty (-> ``[]``), ``all``/``true``/``1``
    (-> every advertised model), or a CSV of ``measure:model`` pairs. Unknown
    measures, models off the allow-list, and malformed entries are logged and
    skipped (never fatal — a warm start / pre-cache must never break boot).
    ``raw=None`` reads the env.
    """
    import logging
    import re

    logger = logging.getLogger(__name__)
    if raw is None:
        raw = os.environ.get(HF_PRELOAD_ENV, "")

    value = raw.strip()
    if value.lower() in ("", "off", "none", "false", "0"):
        return []
    if value.lower() in ("all", "true", "1"):
        return [(m, n) for m, names in _DFLT_PRELOAD_HF.items() for n in names]

    selected: list[tuple[str, str]] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        match = re.match(r"^([^:/]+):(.+)$", entry)
        if not match:
            logger.warning("HF_PRELOAD: ignoring malformed entry %r (expected measure:model)", entry)
            continue
        measure, model = match.group(1).strip(), match.group(2).strip()
        if measure not in _ALLOWED_BASE_MODELS:
            logger.warning("HF_PRELOAD: unknown measure %r; ignoring %r", measure, entry)
            continue
        # Map semantic_search / sbert_cosine onto the shared SBERT loader while
        # still returning the caller's original measure name.
        loader_key = "sbert_cosine" if measure in _semantic_search_measures() else measure
        allowed = _ALLOWED_BASE_MODELS.get(loader_key)
        base = _normalize_hf_name(model)
        if allowed is None or base not in allowed:
            logger.warning(
                "HF_PRELOAD: model %r not on the allow-list for measure %r; ignoring %r",
                model,
                measure,
                entry,
            )
            continue
        selected.append((measure, model))
    return selected


def is_warm() -> bool:
    """Whether the configured ``HF_PRELOAD`` profile warms any model (for /metrics).

    True when the baked-in profile is ``all`` or a non-empty partial list;
    False for ``off``. Note this reports the *configured* selection, not
    whether those models actually finished loading (see ``cache_summary``).
    """
    return bool(_preload_entries(None))


def load_model(measure: str, model_name: str) -> None:
    """Load a single model into the process cache (RAM warm-start step).

    Dispatches on the measure to the right loader: SBERT measures through
    ``get_sbert_model``, cross-encoder through ``get_cross_encoder_model``, and
    bertscore through its module-level singleton scorer. Raises on failure so
    the caller decides how to handle it.
    """
    if measure in _semantic_search_measures():
        get_sbert_model(model_name)
    elif measure == "cross_encoder":
        get_cross_encoder_model(model_name)
    elif measure == "bertscore":
        # BERTScore keeps roberta-large in its own module-level cache, not via
        # ``_get``, so never call the lazy getter; wrap a scorer directly (this
        # loads the checkpoint + tokenizer into the module-level singleton).
        from bert_score import BERTScorer

        BERTScorer(lang="en", model_type=model_name)
    else:  # pragma: no cover - guarded by _preload_entries validation
        raise ValueError(f"no loader for measure {measure!r}")


def warm_start() -> None:
    """Load the selected HF models into RAM at startup (``HF_PRELOAD``).

    The selection comes from the ``HF_PRELOAD`` env (baked in at build time):
    ``off`` (default = cold), ``all``, or a partial ``measure:model`` list.
    Returns without doing anything when the selection is empty, when the
    optional PyTorch stack is not installed, or when a model fails to load (a
    warm start must never prevent the app from booting — it relaxes to lazy
    loading for that model). Logs each model as it is loaded so operators can
    observe the warm-up.
    """
    import logging

    logger = logging.getLogger(__name__)
    for measure, model_name in _preload_entries(None):
        try:
            load_model(measure, model_name)
            logger.info("warm-start loaded %s(%s)", measure, model_name)
        except Exception:  # noqa: BLE001  # warm start must be non-fatal
            logger.warning("warm-start failed for %s(%s); models stay lazy", measure, model_name)


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
