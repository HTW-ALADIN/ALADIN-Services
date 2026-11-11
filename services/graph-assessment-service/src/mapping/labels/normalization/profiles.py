'''Normalization profiles -- named groups of text transformations.'''
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Union

from .lang import Language
from .lang import get as _get_lang
from .ops import apply_ops, check_ops

#: Default cascade for matching -- ordered from strict/exact to loose/soft.
#: The last stage is ``lemmatized``, not ``stemmed``.
CASCADE: tuple[str, ...] = (
    "exact", "whitespace", "relaxed", "diacritics", "stopwords", "lemmatized",
)

#: Comparison-only profiles. Rules of their own, not part of the cascade,
#: never run automatically in the default matching. ``stemmed`` is kept here
#: to compare against ``lemmatized``.
MEASUREMENT: tuple[str, ...] = ("ts1", "ts2", "ts3", "stemmed")

#: Input profiles of the semantic steps. They never pair and are therefore
#: not in CASCADE.
#:
#: ``whitespace_lemma`` is ``whitespace`` plus lemmatization -- not folded and
#: not joined, because a wordnet normalizes its search forms itself.
INPUT: tuple[str, ...] = ("whitespace_lemma",)

#: Central registry of all available profiles and their sequences of operations.
PROFILES: dict[str, tuple[str, ...]] = {
    # -- cascade profiles ---------------------------------------------- #
    "exact":      ("nfc", "trim", "case"),
    "whitespace": ("nfc", "trim", "case", "ws"),
    "relaxed":    ("nfc", "trim", "case", "ws", "punct", "join"),
    "diacritics": ("nfc", "trim", "case", "ws", "punct", "fold", "join"),
    "stopwords":  ("nfc", "trim", "case", "ws", "punct", "fold", "stop", "join"),
    "lemmatized": ("nfc", "trim", "case", "ws", "punct", "fold", "stop", "lemma", "join"),
    # -- comparison profiles ------------------------------------------- #
    # Same ops as "lemmatized" except the second to last position: there the
    # suffix stripping takes the place of the reduction to a known base form.
    "stemmed":    ("nfc", "trim", "case", "ws", "punct", "fold", "stop", "stem", "join"),
    # Three fixed comparison levels TS1 to TS3.
    # TS1 matches "exact" in content (its own name so it can be compared).
    # NFC is always included as a technical precondition.
    "ts1":        ("nfc", "trim", "case"),
    "ts2":        ("nfc", "trim", "case", "punct", "stop_js", "join"),
    "ts3":        ("nfc", "trim", "case", "punct", "stop_js", "stem", "join"),
    # -- input profiles ------------------------------------------------ #
    "whitespace_lemma": ("nfc", "trim", "case", "ws", "lemma"),
}

# Every profile is validated right at import:
# checks e.g. for known operations, correct order and duplicates.
for _name, _ops in PROFILES.items():
    check_ops(_ops)
del _name, _ops


class ProfileError(ValueError):
    """Raised when a profile list is configured incorrectly."""


class UnknownProfileError(ProfileError):
    """Raised when a requested profile does not exist."""


def _check_registration() -> None:
    '''Checks at start that every profile belongs to exactly one list.'''
    named = CASCADE + MEASUREMENT + INPUT
    missing = [p for p in named if p not in PROFILES]
    duplicate = sorted({p for p in named if named.count(p) > 1})
    unregistered = sorted(set(PROFILES) - set(named))
    if missing or duplicate or unregistered:
        raise RuntimeError(
            "profiles: registry and lists disagree. "
            f"Named but not in PROFILES: {missing or '-'}. "
            f"In more than one list: {duplicate or '-'}. "
            f"In PROFILES but in no list: {unregistered or '-'}."
        )


_check_registration()


def ops_for(profile: str) -> tuple[str, ...]:
    """Returns the list of single operations for a profile.

    Raises 'UnknownProfileError' if the profile name does not exist.
    """
    try:
        return PROFILES[profile]
    except KeyError:
        raise UnknownProfileError(
            f"Unknown normalization profile {profile!r}. "
            f"Known: {', '.join(sorted(PROFILES))}."
        ) from None


def check_profiles(profiles: Iterable[str]) -> tuple[str, ...]:
    '''Checks a list of profile names and returns it as a tuple.'''
    seq = tuple(profiles)
    for p in seq:
        ops_for(p)

    duplicate = sorted({p for p in seq if seq.count(p) > 1})
    if duplicate:
        raise ProfileError(
            f"Profile listed twice in {seq}: {duplicate}. Every profile runs on "
            "the rest of the previous one -- a second pass of the same profile "
            "finds nothing more."
        )

    positions = [CASCADE.index(p) for p in seq if p in CASCADE]
    if positions != sorted(positions):
        raise ProfileError(
            f"Profile list {seq} is not in cascade order "
            f"({' -> '.join(CASCADE)}). The order matters: every profile only "
            "runs on what the previous one left over. "
            f"Exempt from the rule are the comparison and input profiles "
            f"({', '.join(MEASUREMENT + INPUT)})."
        )
    return seq


@lru_cache(maxsize=200_000)
def _normalize_cached(s: str, profile: str, lang: Language) -> str:
    return apply_ops(s, ops_for(profile), lang)


def normalize(s: str, profile: str, lang: Union[str, Language]) -> str:
    '''Applies one normalization profile to the text 's'.'''
    return _normalize_cached(s, profile, _get_lang(lang))


def normalize_all(
    s: str,
    profiles: Iterable[str] = CASCADE,
    *,
    lang: Union[str, Language],
) -> dict[str, str]:
    '''Applies several profiles to a text 's'.'''
    resolved = _get_lang(lang)
    return {p: _normalize_cached(s, p, resolved) for p in profiles}
