'''
The label slot: do two labels say the same thing?

Four questions, from the strongest to the weakest evidence:

    exact_label     equal except for surrounding whitespace and case --
                    "Auto" and " auto"
    same_label      equal after the whole normalization cascade --
                    "Rückgabedatum"/"Rueckgabe-Datum", "Kunden"/"Kunde"
    same_meaning    the wordnet names a synonym -- "Ort"/"Standort"
    is_compound_of  one is the head of the other ("Datum"/"Mietdatum")
                    or both have the same head ("DatBeginn"/"Mietbeginn")

Alongside, and explicitly not a filter:

    label_similarity  how similar two labels look -- only orders what the
                      structure has already proven interchangeable

Only the selection lives here: which language, which profiles, which
methods, where the data lives. The methods themselves are in the
subpackages normalization/ and semantics/; the knowledge base lives in
-> src/knowledge.
'''

from functools import cache

from src import config
from .normalization import CASCADE, INPUT, get_language, normalize
from .semantics import (ResourceSpec, SemanticConfig, build_backend,
                        compound, load_resource, spec_for)
from src.knowledge.wordnet import DATA_DIR as WN_DATA

# The language of the labels. A switch for it comes when a second language is
# added; the registry takes it (-> normalization/lang/__init__.py: register).
# So far only German is needed.
LANGUAGE = "de"

# The two ends of the cascade from src/mapping/labels/normalization/profiles.py.
# If one stage makes two labels equal, all later stages do too -- the cascade
# gets looser, never stricter. So the two ends are enough for filtering: the
# strict end as a filter of its own ("exact"), the loose one finds everything
# any stage finds ("label"). Whoever wants to evaluate an intermediate stage
# adds it here.
EXACT_PROFILE = CASCADE[0]      # "exact":      nfc, trim, case
LABEL_PROFILE = CASCADE[-1]     # "lemmatized": ... punct, fold, stop, lemma, join

# The input profile of the knowledge base and the compound: not folded and
# not joined, because a wordnet normalizes its search forms itself.
INPUT_PROFILE = INPUT[0]


def active_stages():
    '''
    The methods of the knowledge base, in the order they are asked.

    Which ones these are is set in -> config.py (SEMANTIC_STAGES), not here:
    the registry has three stages, by default only the synonymy from the
    wordnet runs. An empty tuple means that same_meaning always says no.
    '''
    return tuple(config.SEMANTIC_STAGES)


#: Where the knowledge base lives: one line per resource a stage can name.
#: The wordnet database is known to src/knowledge/wordnet (created with
#: "python -m src.knowledge.wordnet"; $SEMANTICS_WN_DATA takes precedence).
#: Here the path is only handed on to the semantics -- explicitly and never
#: none at all, otherwise "wn" falls back to ~/.wn_data and downloads from the
#: network at runtime.
_RESOURCES = {
    "odenet": ResourceSpec(path=str(WN_DATA)),
}


def normal_form(label):
    '''A label in the input form of the knowledge base.'''
    return _normalized(label, INPUT_PROFILE)


def exact_label(a, b):
    '''Are the two labels equal except for surrounding whitespace and case?'''
    return _same_under(EXACT_PROFILE, a, b)


def same_label(a, b):
    '''
    Do the two labels have the same form after the whole cascade?

    Two empty labels are not the same: they are not equal just because both
    lack the same thing.
    '''
    return _same_under(LABEL_PROFILE, a, b)


def same_meaning(a, b):
    '''
    Do these two labels mean the same? -- the knowledge base answers.

    A yes from any of the active methods is enough. The result is a yes/no
    and no ranking -- the filter filters, it does not score.
    '''
    normal_a, normal_b = normal_form(a), normal_form(b)

    if not (normal_a and normal_b):
        return False

    return any(backend.relate(normal_a, normal_b).matched
               for backend in _backends())


def is_compound_of(a, b):
    '''
    Is one label a compound with the other as its head -- or are both
    compounds with the same head?

    "Datum"/"Mietdatum", but also "Behandl-Katalog"/"Behandlungskatalog"
    and "DatBeginn"/"Mietbeginn". The second half (same_head) catches
    abbreviations and renamings on the same base word -- reference solutions
    abbreviate too.
    -> semantics/compound.py
    '''
    normal_a, normal_b = normal_form(a), normal_form(b)

    return (compound.is_compound_of(normal_a, normal_b, _lemmas())
            or compound.same_head(normal_a, normal_b, _lemmas()))


def label_similarity(a, b):
    '''
    How similar do two labels look? -- 0.0 to 1.0.

    NOT a filter: a pair never comes about here. The number only orders
    within a group whose candidates the structure has already proven
    interchangeable (interchange.py) -- there the choice would otherwise be
    a coin toss, and an order cannot be worse than a coin toss on average.

    Dice coefficient over character bigrams of the normalized form: no
    language, no word list, no domain. "Mietbeginn" is closer to "DatBeginn"
    than "FIN", and the number is not meant to say more than that.
    '''
    grams_a = _bigrams(_normalized(a, LABEL_PROFILE))
    grams_b = _bigrams(_normalized(b, LABEL_PROFILE))

    if not grams_a or not grams_b:
        return 0.0

    return 2 * len(grams_a & grams_b) / (len(grams_a) + len(grams_b))


def _bigrams(text):
    '''The character bigrams as a set; a single character counts on its own.'''
    if len(text) < 2:
        return {text} if text else set()

    return {text[i:i + 2] for i in range(len(text) - 1)}


def _lemmas():
    return get_language(LANGUAGE).lemmas


def _same_under(profile, a, b):
    normal_a = _normalized(a, profile)

    return bool(normal_a) and normal_a == _normalized(b, profile)


def _normalized(label, profile):
    return normalize(str(label or ""), profile, get_language(LANGUAGE))


def _backends():
    '''The active methods -- built once per stage list.'''
    return _built(active_stages())


@cache
def _built(stages):
    '''
    The methods for this stage list, built and cached.

    The cache depends on the list and not on the module: whoever changes
    config.SEMANTIC_STAGES gets the new methods on the next call and does not
    have to clear anything by hand. An empty list gives an empty tuple --
    same_meaning then always says no.
    '''
    cfg = SemanticConfig(stages=list(stages), input_profile=INPUT_PROFILE,
                         resources=dict(_RESOURCES))
    language = get_language(LANGUAGE)
    built = []

    for stage in cfg.active_stages:
        # Two different "specs", and mixing them up costs a debugging session:
        # the StageSpec says WHICH method runs on which knowledge base; the
        # ResourceSpec says WHERE that knowledge base lives. Without the
        # second, the loader only looks under $SEMANTICS_WN_DATA and finds
        # nothing.
        stage_spec = spec_for(stage)
        where = cfg.resources.get(stage_spec.resource)
        resource = load_resource(stage_spec.resource, stage_spec.backend, spec=where,
                                 profile=cfg.input_profile, lang=language)
        built.append(build_backend(stage, resource, cfg=cfg, spec=stage_spec))

    return tuple(built)
