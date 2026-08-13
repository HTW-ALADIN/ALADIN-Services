"""Lexical relations computation implementations for Tier 1 (Spec A).

Each function takes input dict and params dict, returns a result dict
with the set of related words/synsets.
"""

import time
from typing import Any


def _synonym_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    word = input_data.get("word", "")
    lang = params.get("lang", "eng")

    synonyms: set[str] = set()
    for synset in wn.synsets(word):
        for lemma in synset.lemmas(lang=lang):
            name = lemma.name().replace("_", " ")
            if name.lower() != word.lower():
                synonyms.add(name)

    return {"word": word, "relations": sorted(synonyms), "count": len(synonyms)}


def _antonym_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    word = input_data.get("word", "")

    antonyms: set[str] = set()
    for synset in wn.synsets(word):
        for lemma in synset.lemmas():
            for antonym in lemma.antonyms():
                name = antonym.name().replace("_", " ")
                antonyms.add(name)

    return {"word": word, "relations": sorted(antonyms), "count": len(antonyms)}


def _hypernym_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    word = input_data.get("word", "")

    hypernyms: set[str] = set()
    for synset in wn.synsets(word):
        for hypernym in synset.hypernyms():
            for lemma in hypernym.lemmas():
                name = lemma.name().replace("_", " ")
                hypernyms.add(name)

    return {"word": word, "relations": sorted(hypernyms), "count": len(hypernyms)}


def _hyponym_nltk(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from nltk.corpus import wordnet as wn

    word = input_data.get("word", "")

    hyponyms: set[str] = set()
    for synset in wn.synsets(word):
        for hyponym in synset.hyponyms():
            for lemma in hyponym.lemmas():
                name = lemma.name().replace("_", " ")
                hyponyms.add(name)

    return {"word": word, "relations": sorted(hyponyms), "count": len(hyponyms)}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

LEXICAL_DISPATCH: dict[tuple[str, str], Any] = {
    ("synonym", "nltk"): _synonym_nltk,
    ("antonym", "nltk"): _antonym_nltk,
    ("hypernym", "nltk"): _hypernym_nltk,
    ("hyponym", "nltk"): _hyponym_nltk,
}

DEFAULT_LEXICAL_BACKENDS: dict[str, str] = {
    "synonym": "nltk",
    "antonym": "nltk",
    "hypernym": "nltk",
    "hyponym": "nltk",
}


def compute_lexical(relation: str, backend: str | None, input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Compute a lexical relations operation and return the result dict."""
    if backend is None:
        backend = DEFAULT_LEXICAL_BACKENDS.get(relation, "nltk")

    key = (relation, backend)
    func = LEXICAL_DISPATCH.get(key)
    if func is None:
        raise ValueError(f"Unsupported combination: relation={relation}, backend={backend}")

    start = time.monotonic()
    result = func(input_data, params)
    elapsed = time.monotonic() - start
    result["compute_time_ms"] = round(elapsed * 1000, 2)
    return result
