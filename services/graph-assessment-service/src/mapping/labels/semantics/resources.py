'''Find and load the knowledge base -- in normal operation the wordnet.'''
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from ..normalization.lang import Language
from . import wn_adapter as wordnet_mod
from .config import ResourceSpec
from .stages import BACKEND_WORDNET
from .wn_adapter import WordNetError, WordNetResource

#: Where the wordnet database lives. **There is deliberately no default path.**
#: ``wn`` would otherwise fall back to ``~/.wn_data`` and download from the
#: network on first access -- exactly the way a network call would end up in
#: the middle of a comparison (determinism). The variable is set from outside;
#: without it the caller passes the path from ``src.knowledge.wordnet.DATA_DIR``
#: as ``ResourceSpec.path``.
WN_DATA_ENV = "SEMANTICS_WN_DATA"

#: The file name under which ``wn`` creates its database. We check it before
#: touching ``wn`` at all: accessing an empty directory would otherwise create
#: the database as a side effect, and "data missing" would turn into "data
#: there, but empty" -- two different findings.
WN_DB_NAME = "wn.db"

#: The manifest that ``src/knowledge/wordnet/fetch.py`` stores when loading.
WN_MANIFEST_NAME = "manifest.json"


class ResourceError(ValueError):
    """A resource cannot be loaded."""


class MissingResourceError(ResourceError):
    '''The resource is configured, but there is no file for it.'''


# --------------------------------------------------------------------------- #
# Finding
# --------------------------------------------------------------------------- #

def locate_dir(name: str, spec: Optional[ResourceSpec] = None) -> Optional[Path]:
    '''Where does a resource **directory** live? ``None`` if nowhere.'''
    raw = (spec.path if spec is not None and spec.path
           else os.environ.get(WN_DATA_ENV, ""))
    if not raw:
        return None
    found_path = Path(raw).expanduser()
    return found_path if found_path.is_dir() else None


# --------------------------------------------------------------------------- #
# Loading: wordnet
# --------------------------------------------------------------------------- #

#: Opened wordnets, kept by (directory, ID). Unlike a lexicon, profile and
#: language are NOT in the key: the terms of the resource are not normalized
#: here, because they live in a database we do not own. ``wn`` normalizes the
#: lookup itself.
_WN_CACHE: dict[tuple[str, str], WordNetResource] = {}


def _wn_manifest(data_dir: Path, specifier: str) -> dict:
    """The manifest entry for an ID. Empty if there is none."""
    found_path = data_dir / WN_MANIFEST_NAME
    if not found_path.is_file():
        return {}
    try:
        data = json.loads(found_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw_entries = data.get("lexicons")
    if not isinstance(raw_entries, dict):
        return {}
    entry = raw_entries.get(specifier)
    return entry if isinstance(entry, dict) else {}


def _wn_fingerprint(entry: dict, specifier: str) -> tuple[str, str]:
    '''``(fingerprint, note)`` -- and which of the two cases it was.'''
    raw = entry.get("lmf_sha256")
    if isinstance(raw, str) and raw:
        return f"sha256:{raw[:16]}", ""
    short_form = hashlib.sha256(specifier.encode("utf-8")).hexdigest()[:16]
    return (
        f"sha256:{short_form}",
        f"Built without a build manifest ({WN_MANIFEST_NAME}): the fingerprint "
        f"is a hash over the ID {specifier!r}, not a hash over the data. It "
        f"tells versions apart, but not two deliveries of the same version.",
    )


def load_wordnet(name: str, *, spec: Optional[ResourceSpec] = None) -> WordNetResource:
    '''Open a wordnet from the local data directory.'''
    if not wordnet_mod.AVAILABLE:
        raise MissingResourceError(
            f"Resource {name!r} needs the library 'wn', which is not "
            f"installed. It is listed in pyproject.toml."
        )

    data_dir = locate_dir(name, spec)
    if data_dir is None:
        origin = (f"path {spec.path!r}" if spec is not None and spec.path
                 else f"${WN_DATA_ENV}")
        raise MissingResourceError(
            f"Resource {name!r}: no wordnet data directory under {origin}. "
            f"The data is put into the data directory once in advance "
            f"(python -m src.knowledge.wordnet); there is deliberately no "
            f"default path, because falling back to ~/.wn_data led to a "
            f"download at runtime."
        )

    if not (data_dir / WN_DB_NAME).is_file():
        raise MissingResourceError(
            f"Resource {name!r}: {data_dir} contains no {WN_DB_NAME}. "
            f"Create it with 'python -m src.knowledge.wordnet --dir {data_dir}'."
        )

    requested = f"{name}:{spec.version}" if spec is not None and spec.version else name
    key = (str(data_dir), requested)
    hit = _WN_CACHE.get(key)
    if hit is not None:
        return hit

    wordnet_mod.configure(data_dir)

    try:
        # First the full ID, then the evidence, then the resource: the
        # manifest entry is under ``odenet:1.4``, even if someone only asked
        # for ``odenet``.
        specifier = wordnet_mod.resolve_specifier(requested)
        entry = _wn_manifest(data_dir, specifier)
        fingerprint, note = _wn_fingerprint(entry, specifier)
        res = wordnet_mod.open_wordnet(
            name, specifier,
            fingerprint=fingerprint,
            size=entry.get("synsets"),
            note=note,
        )
    except WordNetError as exc:
        raise MissingResourceError(f"Resource {name!r} ({data_dir}): {exc}") from exc

    _WN_CACHE[key] = res
    return res


# --------------------------------------------------------------------------- #
# One entry point for all kinds
# --------------------------------------------------------------------------- #

def load_resource(name: str, backend: str, *, profile: str, lang: Language,
                  spec: Optional[ResourceSpec] = None) -> WordNetResource:
    '''
    Load the resource that belongs to this backend -- in normal operation
    only the wordnet. ``profile`` and ``lang`` stay in the signature: a
    lexicon normalized its terms when loading, the wordnet does that itself.
    '''
    if backend == BACKEND_WORDNET:
        return load_wordnet(name, spec=spec)
    raise ResourceError(
        f"Resource {name!r}: there is no loader for the backend {backend!r}. "
        f"Known: {BACKEND_WORDNET}."
    )


def clear_cache() -> None:
    """Clear the resource cache. For tests that swap data underneath us."""
    _WN_CACHE.clear()
