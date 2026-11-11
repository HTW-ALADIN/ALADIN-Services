'''Language registry -- the language-bound data of the normalization.'''
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .lexicon import Lexicon, LexiconError


@dataclass(frozen=True)
class Language:
    '''The language-bound data of a normalization.'''

    name: str
    stopwords: frozenset[str]
    suffixes: tuple[str, ...]
    min_stem: int
    char_map: tuple[tuple[str, str], ...] = ()
    lemmas: Optional[Lexicon] = None
    lemma_rules: tuple[tuple[str, tuple[str, ...]], ...] = ()
    umlaut_reversal: tuple[tuple[str, str], ...] = ()


# The registry is filled below, after ``Language`` is defined -- the language
# modules import the type from here.
_LANGUAGES: dict[str, Language] = {}


def register(language: Language) -> None:
    """Register a language under its name."""
    _LANGUAGES[language.name] = language


def get(language: Union[str, Language]) -> Language:
    '''Resolve a language name.'''
    if isinstance(language, Language):
        return language
    if language is None:
        raise ValueError(
            f"A language must be given. Known: {', '.join(sorted(_LANGUAGES))}."
        )
    try:
        return _LANGUAGES[language]
    except KeyError:
        raise ValueError(
            f"Unknown language {language!r}. Known: {', '.join(sorted(_LANGUAGES))}."
        ) from None


def known() -> tuple[str, ...]:
    return tuple(sorted(_LANGUAGES))


# There is no default here: which language applies is decided by the caller
# (-> src/mapping/labels/label_match.py: LANGUAGE).

# Only importable after the type definition -- the language modules take
# ``Language`` from here. The same place is the extension point: another
# language is one module plus one ``register`` line.
from .de import DE  # noqa: E402

register(DE)

__all__ = [
    "DE",
    "Language",
    "Lexicon",
    "LexiconError",
    "get",
    "known",
    "register",
]
