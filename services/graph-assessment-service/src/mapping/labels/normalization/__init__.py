'''
Normalization of labels -- a plain text library.

    profiles.py  the cascade: named sequences of operations (normalize)
    ops.py       the single operations (nfc, trim, case, punct, fold, ...)
    lang/        the language-bound data (stopwords, umlauts, lemma list)

Asked by -> src/mapping/labels/label_match.py, which offers the two ends of
the cascade as predicates (exact_label, same_label).
'''
from __future__ import annotations

from .lang import Language, Lexicon
from .lang import get as get_language
from .ops import (CANONICAL_ORDER, EXCLUSIVE_OPS, MANDATORY_OPS, OPS,
                  MissingLexiconError, OpError, apply_ops, check_ops)
from .profiles import (CASCADE, INPUT, MEASUREMENT, PROFILES, ProfileError,
                       UnknownProfileError, check_profiles, normalize,
                       normalize_all, ops_for)

__all__ = [
    "CANONICAL_ORDER",
    "CASCADE",
    "EXCLUSIVE_OPS",
    "INPUT",
    "MANDATORY_OPS",
    "MEASUREMENT",
    "Lexicon",
    "MissingLexiconError",
    "OPS",
    "OpError",
    "PROFILES",
    "ProfileError",
    "UnknownProfileError",
    "Language",
    "apply_ops",
    "check_ops",
    "check_profiles",
    "get_language",
    "normalize",
    "normalize_all",
    "ops_for",
]
