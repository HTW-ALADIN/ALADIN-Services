'''The lemma list of a language -- a set to check against, not a table of forms.'''
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

#: We live in ``lang/``, so ``data/`` next to it is the root of the shipped
#: lists. Resolved by name and not by a working-directory path -- that would
#: depend on where someone starts from.
DATA_DIR = Path(__file__).resolve().parent / "data"


class LexiconError(ValueError):
    """The list cannot be loaded or does not hold what it promises."""


@dataclass(frozen=True)
class Lexicon:
    '''A lemma list: identity outside, a set inside.'''

    name: str
    digest: str
    words: frozenset[str] = field(compare=False, repr=False)

    def __contains__(self, word: str) -> bool:
        return word in self.words

    def __len__(self) -> int:
        return len(self.words)


def _digest(lemmas: list[str]) -> str:
    """Must compute exactly like ``build_lemmas.py`` next door."""
    return f"sha256:{hashlib.sha256(chr(10).join(lemmas).encode('utf-8')).hexdigest()}"


def load(name: str) -> Lexicon:
    '''Load the shipped list ``name`` from ``lang/data/``.'''
    path = DATA_DIR / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LexiconError(
            f"Lemma list {name!r} not found ({path}). Generate it with:\n"
            f"    python -m src.mapping.labels.normalization.lang.build_lemmas"
        ) from None
    except json.JSONDecodeError as exc:
        raise LexiconError(f"Lemma list {path} is not valid JSON: {exc}") from None

    lemmas = data.get("lemmas")
    meta = data.get("meta") or {}
    if not isinstance(lemmas, list) or not lemmas:
        raise LexiconError(f"Lemma list {path} contains no list 'lemmas'.")

    computed = _digest(lemmas)
    recorded = meta.get("digest")
    if recorded and recorded != computed:
        raise LexiconError(
            f"Lemma list {path} does not match its fingerprint.\n"
            f"  recorded in header: {recorded}\n"
            f"  recomputed        : {computed}\n"
            "The file was changed after it was generated. Generate it again "
            "with build_lemmas.py next door."
        )

    return Lexicon(
        name=meta.get("name") or name,
        digest=computed,
        words=frozenset(lemmas),
    )
