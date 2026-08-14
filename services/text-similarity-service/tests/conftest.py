"""Shared test fixtures.

Ensures the small NLTK corpora (WordNet + WordNet IC) needed by the
wordnet-based measures are available before the suite runs. These are tiny
(WordNet is ~10 MB) and are downloaded once, on demand, matching the service's
"download data on first use" model. The large model resources (HuggingFace,
gensim, Odenet) are deliberately NOT fetched here — those remain gated by
their respective cost/extra mechanisms.
"""

import nltk
import pytest

_NLTK_RESOURCES = ["wordnet", "wordnet_ic"]


@pytest.fixture(scope="session", autouse=True)
def _nltk_wordnet_data():
    for resource in _NLTK_RESOURCES:
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True, raise_on_error=True)
