'''
The atomic operations, their canonical order and the check.

Every operation is one step of the normalization: string in, string out.
Which of them run in which order is set by a profile (-> profiles.py); only
what the single steps do lives here.

The functions are in the same order as ``CANONICAL_ORDER`` at the bottom --
whoever reads the cascade from top to bottom reads the file from top to
bottom.
'''
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable

from .lang import Language

# --------------------------------------------------------------------------- #
# Separators -- the basis of several operations
# --------------------------------------------------------------------------- #

#: The set of separators, as an expression. It exists exactly once in the
#: tree: it is the **target** of ``punct`` and the **word boundary** of the
#: token operations -- if the two sets drift apart, ``stop`` finds no word
#: boundaries any more and silently normalizes nonsense. So the two patterns
#: below are built from the same character class and not written twice.
_SEPARATOR_CLASS = r"[-\s._/]+"

#: Separators for tokenizing: runs of hyphens, spaces/tabs, dots, underscores
#: or slashes.
_SEPARATORS = re.compile(_SEPARATOR_CLASS)

#: The same pattern, but as a group: ``re.split`` then returns the separators
#: too instead of swallowing them. See ``_map_tokens``.
_SEPARATORS_KEEP = re.compile(f"({_SEPARATOR_CLASS})")

#: Plain whitespace (spaces, tabs, line breaks). Used when only whitespace is
#: to be cleaned up or joined, without deleting special characters.
_WHITESPACE = re.compile(r"\s+")


def _tokens(s: str) -> list[str]:
    '''Splits a text into single words (tokens) at the defined separators.'''
    return [t for t in _SEPARATORS.split(s) if t]


def _map_tokens(s: str, fn) -> str:
    '''Applies ``fn`` to every word and leaves the separators in place.'''
    # ``re.split`` with a group returns word, separator, word, ... in turn.
    # The odd positions are the separators and stay untouched.
    parts = _SEPARATORS_KEEP.split(s)
    return "".join(part if i % 2 else fn(part) for i, part in enumerate(parts))


# --------------------------------------------------------------------------- #
# The operations, in canonical order
# --------------------------------------------------------------------------- #

def op_nfc(s: str, lang: Language) -> str:
    """``nfc`` -- Unicode composition: decomposed ``u`` + combining diaeresis -> ``ü``."""
    return unicodedata.normalize("NFC", s)


def op_trim(s: str, lang: Language) -> str:
    '''``trim`` -- removes whitespace at the edges of a string.'''
    return s.strip()


def op_case(s: str, lang: Language) -> str:
    """``case`` -- lower case: ``Kunde`` -> ``kunde``."""
    return s.lower()


def op_ws(s: str, lang: Language) -> str:
    """``ws`` -- runs of whitespace to ONE space: ``"Kunden\\nNr"`` -> ``"Kunden Nr"``."""
    return _WHITESPACE.sub(" ", s).strip()


def op_punct(s: str, lang: Language) -> str:
    """``punct`` -- separators to one space: ``mit_arbeiter`` -> ``mit arbeiter``."""
    return _SEPARATORS.sub(" ", s)


def op_fold(s: str, lang: Language) -> str:
    """``fold`` -- resolve umlauts, then fold diacritics.

    ``Rückgabe`` -> ``rueckgabe`` (after ``case``), ``Café`` -> ``cafe``.
    """
    for src, dst in lang.char_map:
        s = s.replace(src, dst)
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _split_stopwords(s: str, lang: Language) -> tuple[list[str], list[str]]:
    """Splits the text and returns two lists: ``(all words, words without stopwords)``."""
    toks = _tokens(s)
    return toks, [t for t in toks if t not in lang.stopwords]


def op_stop(s: str, lang: Language) -> str:
    """``stop`` -- remove stopwords, with fallback.

    If the text would be empty afterwards, the original text is kept.
    """
    toks, kept = _split_stopwords(s, lang)
    return " ".join(kept or toks)


def op_stop_js(s: str, lang: Language) -> str:
    """``stop_js`` -- remove stopwords strictly, without fallback.

    A text made only of stopwords such as ``"der die"`` becomes ``""``.
    """
    _, kept = _split_stopwords(s, lang)
    return " ".join(kept)


def fallback_tokens(s: str, lang: Language) -> list[str]:
    '''Returns the words kept by the fallback in ``op_stop``, otherwise ``[]``.'''
    toks, kept = _split_stopwords(s, lang)
    return toks if toks and not kept else []


def _stem_token(token: str, lang: Language) -> str:
    """Removes the longest matching ending of the word. At most one ending is removed."""
    for suffix in lang.suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= lang.min_stem:
            return token[: -len(suffix)]
    return token


def op_stem(s: str, lang: Language) -> str:
    """``stem`` -- remove word endings: ``kunden nummer`` -> ``kund nummer``.

    In normal operation ``lemma`` runs instead; ``stem`` is kept for
    comparison (-> profiles.py: MEASUREMENT).
    """
    return " ".join(_stem_token(t, lang) for t in _tokens(s))


class MissingLexiconError(ValueError):
    '''The language has no lemma list, but the profile requires ``lemma``.'''


def _without_umlaut(stem: str, lang: Language) -> str:
    """Undoes the plural umlaut: ``vertraeg`` -> ``vertrag``."""
    for umlaut, base in lang.umlaut_reversal:
        stem = stem.replace(umlaut, base)
    return stem


def _candidates(token: str, lang: Language):
    '''The possible base forms of a token, in the order they are checked.'''
    for suffix, replacements in lang.lemma_rules:
        if not token.endswith(suffix):
            continue
        stem = token[: -len(suffix)]
        if len(stem) < lang.min_stem:
            # The same lower bound as for stemming, for the same reason:
            # whatever is left below it is mutilation.
            continue
        without_umlaut = _without_umlaut(stem, lang)
        for replacement in replacements:
            yield stem + replacement
            if without_umlaut != stem:
                yield without_umlaut + replacement


def _lemma_token(token: str, lang: Language) -> str:
    """The first base form the lemma list knows -- otherwise the token itself."""
    known = lang.lemmas
    if token in known:
        # If the token itself is in the list, it already is a base form. The
        # check comes before the rules, not after them: without it 'ende'
        # would become 'end' via the rule "e" -> "" and 'preis' would become
        # 'prei' via "s" -> "" -- both words with nothing to reduce.
        return token
    for candidate in _candidates(token, lang):
        if candidate in known:
            return candidate
    return token


def op_lemma(s: str, lang: Language) -> str:
    """``lemma`` -- reduce every word to its base form (``mietet`` -> ``mieten``).

    Only if there is a known base form.
    """
    if lang.lemmas is None:
        raise MissingLexiconError(
            f"Language {lang.name!r} has no lemma list, but the profile "
            "requires the operation 'lemma'. Either choose a profile without "
            "'lemma' or give the language a lemma list (see "
            "lang/lexicon.py and lang/build_lemmas.py)."
        )
    return _map_tokens(s, lambda t: _lemma_token(t, lang))


def op_join(s: str, lang: Language) -> str:
    """``join`` -- remove spaces without replacement: ``kunden nr`` -> ``kundennr``."""
    return _WHITESPACE.sub("", s)


# --------------------------------------------------------------------------- #
# Registry, order, check
# --------------------------------------------------------------------------- #

#: Canonical order. A profile is a subset of it, applied in exactly this
#: order. ``stop``/``stop_js`` and ``stem``/``lemma`` each stand right next
#: to each other; which of the two comes first does not matter -- they may
#: not occur together anyway (``EXCLUSIVE_OPS``).
CANONICAL_ORDER: tuple[str, ...] = (
    "nfc", "trim", "case", "ws", "punct", "fold", "stop", "stop_js",
    "stem", "lemma", "join",
)

#: Cannot be switched off: a technical precondition, not a decision about
#: content. Without composition a decomposed "ü" already misses its own twin
#: at the first stage.
MANDATORY_OPS: frozenset[str] = frozenset({"nfc"})

#: Groups from which at most one operation may be in the same sequence.
#: ``stop``/``stop_js`` are the same operation with and without fallback,
#: ``stem``/``lemma`` two methods for the same task.
EXCLUSIVE_OPS: tuple[frozenset[str], ...] = (
    frozenset({"stop", "stop_js"}),
    frozenset({"stem", "lemma"}),
)

#: Operations that work on tokens instead of the string. Documentation only
#: -- the implementations split on their own.
TOKEN_OPS: frozenset[str] = frozenset({"stop", "stop_js", "stem", "lemma"})

#: The registry. Entered explicitly so it stays readable next to
#: ``CANONICAL_ORDER`` and a missing entry shows at once.
OPS: dict[str, Callable[[str, Language], str]] = {
    "nfc": op_nfc,
    "trim": op_trim,
    "case": op_case,
    "ws": op_ws,
    "punct": op_punct,
    "fold": op_fold,
    "stop": op_stop,
    "stop_js": op_stop_js,
    "stem": op_stem,
    "lemma": op_lemma,
    "join": op_join,
}


class OpError(ValueError):
    """Unknown operation or a sequence that breaks a rule."""


def _check_registration() -> None:
    '''Order and registry must match exactly.'''
    missing_impl = [o for o in CANONICAL_ORDER if o not in OPS]
    unplaced = sorted(set(OPS) - set(CANONICAL_ORDER))
    if missing_impl or unplaced:
        raise RuntimeError(
            "ops: order and registry disagree. "
            f"In CANONICAL_ORDER but not in OPS: {missing_impl or '-'}. "
            f"In OPS but not in CANONICAL_ORDER: {unplaced or '-'}. "
            "Both have to be entered in ops.py -- there is deliberately no "
            "self-registration."
        )
    undefined = sorted((set(MANDATORY_OPS) | set().union(*EXCLUSIVE_OPS)) - set(OPS))
    if undefined:
        raise RuntimeError(
            f"ops: MANDATORY_OPS/EXCLUSIVE_OPS name unknown operations {undefined}."
        )


_check_registration()


def check_ops(ops: Iterable[str]) -> tuple[str, ...]:
    '''Check a sequence of operations and return it as a tuple.'''
    seq = tuple(ops)
    unknown = [o for o in seq if o not in OPS]
    if unknown:
        raise OpError(
            f"Unknown operation(s) {unknown}. Known: {', '.join(CANONICAL_ORDER)}."
        )
    if len(set(seq)) != len(seq):
        raise OpError(f"Operation listed twice in {seq}.")
    positions = [CANONICAL_ORDER.index(o) for o in seq]
    if positions != sorted(positions):
        raise OpError(
            f"Operation sequence {seq} is not in canonical order "
            f"({' -> '.join(CANONICAL_ORDER)})."
        )
    missing = MANDATORY_OPS - set(seq)
    if missing:
        raise OpError(
            f"Operation sequence {seq} leaves out the mandatory operation(s) "
            f"{sorted(missing)}."
        )
    for group in EXCLUSIVE_OPS:
        both = sorted(group & set(seq))
        if len(both) > 1:
            raise OpError(
                f"Operation sequence {seq} contains {both} -- they exclude "
                f"each other, at most one of them may be in it."
            )
    if "punct" in seq and "join" not in seq:
        raise OpError(
            f"Operation sequence {seq} contains 'punct' but no 'join'. "
            "'punct' turns separators into spaces; without 'join' they stay "
            "and the normal form carries leading, trailing and inner spaces."
        )
    return seq


def apply_ops(s: str, ops: Iterable[str], lang: Language) -> str:
    """Apply ``ops`` in order. Expects a sequence that has already been checked."""
    for op in ops:
        s = OPS[op](s, lang)
    return s


__all__ = [
    "CANONICAL_ORDER",
    "EXCLUSIVE_OPS",
    "MANDATORY_OPS",
    "OPS",
    "TOKEN_OPS",
    "MissingLexiconError",
    "OpError",
    "apply_ops",
    "check_ops",
    "fallback_tokens",
]
