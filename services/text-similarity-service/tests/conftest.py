"""Shared test fixtures.

Ensures the small NLTK corpora (WordNet + WordNet IC) needed by the
wordnet-based measures are available before the suite runs. These are tiny
(WordNet is ~10 MB) and are downloaded once, on demand, matching the service's
"download data on first use" model.

Two robustness concerns are handled here specifically because they break CI
(and fresh local clones) with ``LookupError: Resource 'wordnet' not found``:

1. NLTK >= 3.10 stores downloaded corpora as a ``.zip`` inside ``corpora/`` and
   only resolves a *directory* resource like ``corpora/wordnet`` (no trailing
   slash) once it has been extracted to a plain directory. A bare
   ``nltk.download(...)`` can report success while ``nltk.data.find("corpora/<name>")``
   still fails for a zipped, not-yet-extracted corpus. We therefore force full
   extraction and verify the resource is actually resolvable afterwards.

2. Any test that depends on this data is individually ``skip``-guarded (see
   ``tests/test_similarity.py``), so a fully offline run skips rather than
   hard-fails. This fixture is still worth keeping because it makes the
   data-dependent tests exercise their real behaviour whenever downloading is
   possible (e.g. CI).

The large model resources (HuggingFace, gensim, Odenet) are deliberately NOT
fetched here — those remain gated by their respective cost/extra mechanisms.
"""

import zipfile
from pathlib import Path

import nltk
import pytest

_NLTK_RESOURCES = ["wordnet", "wordnet_ic"]


def _extract_zip(zip_path: Path, dest_root: Path) -> bool:
    """Extract ``zip_path`` into ``dest_root`` so NLTK can resolve the corpus dir."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_root)
        return True
    except (zipfile.BadZipFile, OSError):
        return False


def _ensure_available(resource: str) -> bool:
    """Try to make ``corpora/<resource>`` resolvable; return True on success."""
    try:
        nltk.data.find(f"corpora/{resource}")
        return True
    except LookupError:
        pass

    # Download may have placed only a .zip; force a real download attempt first.
    try:
        nltk.download(resource, quiet=True, raise_on_error=True)
    except Exception:  # noqa: BLE001 - downloader raises on network/parse errors
        pass

    # If it is resolvable now (e.g. extracted by the downloader), we are done.
    try:
        nltk.data.find(f"corpora/{resource}")
        return True
    except LookupError:
        pass

    # Fall back to locating the packed .zip and extracting it ourselves so the
    # resource is a plain directory NLTK can resolve without a trailing slash.
    # Pick a writable corpora dir to extract into; prefer the first NLTK path.
    zip_name = f"{resource}.zip"
    for corpora_dir in [c for c in (Path(p) / "corpora" for p in nltk.data.path) if c.is_dir()]:
        zip_path = corpora_dir / zip_name
        if not zip_path.is_file():
            continue
        if _extract_zip(zip_path, corpora_dir):
            try:
                nltk.data.find(f"corpora/{resource}")
                return True
            except LookupError:
                pass

    return False


@pytest.fixture(scope="session", autouse=True)
def _nltk_wordnet_data():
    for resource in _NLTK_RESOURCES:
        _ensure_available(resource)


@pytest.fixture
def profile_client(request):
    """A TestClient factory for a specific SIMILARITY_PROFILE.

    The profile is baked into module state at import time, so switching it
    requires reloading the catalog + app modules. Call ``profile_client("pytorch")``
    to get a client for that profile, then the default ``cpu`` profile is
    restored after the test.

    When the path ``profile_client`` is parametrized, the parametrized value is
    used as the default before ``profile_client("x")`` overrides it.
    """
    import importlib
    import os

    import src.catalog as catalog
    import src.main as main
    from fastapi.testclient import TestClient

    _DEFAULT = "cpu"
    _param = getattr(request, "param", None)

    def _make(profile: str = _param or _DEFAULT, disable_conceptnet: bool = False) -> TestClient:
        os.environ["SIMILARITY_PROFILE"] = profile
        if disable_conceptnet:
            os.environ["SIMILARITY_DISABLE_LOCAL_CONCEPTNET"] = "true"
        else:
            os.environ.pop("SIMILARITY_DISABLE_LOCAL_CONCEPTNET", None)
        importlib.reload(catalog)
        importlib.reload(main)
        return TestClient(main.app)

    yield _make

    # Restore module state to the default so later tests see a clean cpu app.
    os.environ["SIMILARITY_PROFILE"] = _DEFAULT
    os.environ.pop("SIMILARITY_DISABLE_LOCAL_CONCEPTNET", None)
    importlib.reload(catalog)
    importlib.reload(main)
