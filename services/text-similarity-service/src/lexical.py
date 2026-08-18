"""Lexical relations (synonym/antonym/hypernym/hyponym) via WordNet backends.

English relations use NLTK WordNet (base install). German relations use the
Open German WordNet (Odenet) via the optional ``wn`` library (extra ``de``) —
a free-licensed alternative to GermaNet.
"""

import time

# Published Odenet lexicon id in the ``wn`` index (Free German WordNet).
ODENET_ID = "odenet:1.4"


def _wordnet_relations(input_data: dict[str, Any], params: dict[str, Any], kind: str) -> dict[str, Any]:
    from .model_cache import ensure_wordnet

    ensure_wordnet()
    from nltk.corpus import wordnet as wn

    word = input_data.get("word", "")
    names: set[str] = set()
    for synset in wn.synsets(word):
        if kind == "synonym":
            for lemma in synset.lemmas(lang=params.get("lang", "eng")):
                name = lemma.name().replace("_", " ")
                if name.lower() != word.lower():
                    names.add(name)
        elif kind == "antonym":
            for lemma in synset.lemmas():
                names.update(a.name().replace("_", " ") for a in lemma.antonyms())
        else:
            related = synset.hypernyms() if kind == "hypernym" else synset.hyponyms()
            for syn in related:
                names.update(lemma.name().replace("_", " ") for lemma in syn.lemmas())
    return {"word": word, "relations": sorted(names), "count": len(names)}


def _odenet_relations(input_data: dict[str, Any], params: dict[str, Any], kind: str) -> dict[str, Any]:
    """German lexical relations via Odenet (Open German WordNet, ``wn`` library)."""
    from .model_cache import get_odenet

    de = get_odenet()
    word = input_data.get("word", "")
    names: set[str] = set()
    for synset in de.synsets(word):
        if kind == "synonym":
            for lemma in synset.lemmas():
                name = lemma.replace("_", " ")
                if name.lower() != word.lower():
                    names.add(name)
        elif kind == "antonym":
            # Odenet stores antonyms at the synset level (and sometimes sense
            # level); include both so real data surfaces.
            for related in synset.get_related("antonym"):
                names.update(lemma.replace("_", " ") for lemma in related.lemmas())
            for sense in synset.senses():
                for ant in sense.get_related("antonym"):
                    names.add(ant.word().lemma().replace("_", " "))
        else:
            rel = "hypernym" if kind == "hypernym" else "hyponym"
            for related in synset.get_related(rel):
                names.update(lemma.replace("_", " ") for lemma in related.lemmas())
    return {"word": word, "relations": sorted(names), "count": len(names), "resource": ODENET_ID}


# ─── Dispatcher ───────────────────────────────────────────────────────────────

LEXICAL_DISPATCH: dict[tuple[str, str], Any] = {
    ("synonym", "nltk"): partial(_wordnet_relations, kind="synonym"),
    ("antonym", "nltk"): partial(_wordnet_relations, kind="antonym"),
    ("hypernym", "nltk"): partial(_wordnet_relations, kind="hypernym"),
    ("hyponym", "nltk"): partial(_wordnet_relations, kind="hyponym"),
    ("synonym", "odenet"): partial(_odenet_relations, kind="synonym"),
    ("antonym", "odenet"): partial(_odenet_relations, kind="antonym"),
    ("hypernym", "odenet"): partial(_odenet_relations, kind="hypernym"),
    ("hyponym", "odenet"): partial(_odenet_relations, kind="hyponym"),
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
