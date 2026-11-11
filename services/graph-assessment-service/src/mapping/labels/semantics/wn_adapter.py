'''
The adapter to the library ``wn``: open a wordnet and look things up.

Nothing is compared here, only opened -- set the data directory, resolve
the ID, look up synsets. The comparing happens next door
(-> backends/wordnet.py: the method), and where the data lives and how it
gets there is described in -> src/knowledge/wordnet.
'''
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Optional, Sequence

try:  # pragma: no cover -- the branch itself cannot be tested meaningfully
    import wn as _wn
    AVAILABLE = True
except ImportError:  # pragma: no cover
    _wn = None  # type: ignore[assignment]
    AVAILABLE = False


class WordNetError(ValueError):
    """The wordnet database cannot be opened or interpreted."""


class WordNetHypernyms(Mapping[str, Sequence[str]]):
    '''Synset ID -> more general synsets. The view for ``taxonomy``.'''

    def __init__(self, wordnet: Any) -> None:
        self._wordnet = wordnet
        self._cache: dict[str, tuple[str, ...]] = {}

    def __getitem__(self, synset_id: str) -> tuple[str, ...]:
        hit = self._cache.get(synset_id)
        if hit is not None:
            return hit
        try:
            synset = self._wordnet.synset(synset_id)
        except _wn.Error:
                # ``wn`` raises its own error for an unknown ID; a mapping
                # needs a ``KeyError`` here. Only this one: a blanket
                # ``except Exception`` would turn every operating error into a
                # taxonomy miss.
            raise KeyError(synset_id) from None
        uppers = tuple(sorted(s.id for s in synset.hypernyms()))
        self._cache[synset_id] = uppers
        return uppers

    def __iter__(self) -> Iterator[str]:
        '''All synset IDs, sorted.'''
        return iter(sorted(s.id for s in self._wordnet.synsets()))

    def __len__(self) -> int:
        return len(self._wordnet.synsets())


@dataclass(frozen=True)
class WordNetResource:
    '''An opened wordnet, ready for lookups.'''

    name: str
    specifier: str
    version: Optional[str]
    license: Optional[str]
    fingerprint: str
    size: int
    broader: WordNetHypernyms
    #: Plain text about limitations of the data -- currently the note that
    #: without a build manifest the fingerprint only reflects the ID.
    note: str = ""
    #: The ``wn.Wordnet`` handle. Do not compare, do not print.
    wordnet: Any = field(repr=False, compare=False, default=None)
    #: Term -> synset IDs. Memoized like the hypernym cache; with O(N x M)
    #: pairs the same terms inevitably come up again and again.
    _senses: dict[str, tuple[str, ...]] = field(
        default_factory=dict, repr=False, compare=False,
    )

    def synsets_for(self, term: str) -> tuple[str, ...]:
        '''All senses of a term, **sorted by ID**.'''
        hit = self._senses.get(term)
        if hit is None:
            hit = tuple(sorted(s.id for s in self.wordnet.synsets(term)))
            self._senses[term] = hit
        return hit

    def knows(self, term: str) -> bool:
        """Does the wordnet know the term in any sense?"""
        return bool(self.synsets_for(term))


def _require() -> None:
    if not AVAILABLE:  # pragma: no cover -- see module docstring
        raise WordNetError(
            "The library 'wn' is not installed. It is listed in "
            "pyproject.toml and is needed for the wordnet stages."
        )


def configure(path) -> None:
    '''Set up ``wn``: data directory and access from the thread pool.'''
    _require()
    _wn.config.data_directory = path
    _wn.config.allow_multithreading = True


def resolve_specifier(specifier: str) -> str:
    '''The full ``id:version`` ID for a possibly vague one.'''
    _require()
    loaded = _wn.lexicons(lexicon=specifier)
    if not loaded:
        raise WordNetError(
            f"No lexicon {specifier!r} in the database. Installed: "
            f"{', '.join(sorted(l.specifier() for l in _wn.lexicons())) or '(nothing)'}."
        )
    return loaded[0].specifier()


def open_wordnet(name: str, specifier: str, *, fingerprint: str,
                 size: Optional[int] = None, note: str = "") -> WordNetResource:
    '''Open a lexicon that is already installed in the wordnet database.'''
    _require()
    try:
        wordnet = _wn.Wordnet(lexicon=specifier)
    except Exception as exc:
        raise WordNetError(
            f"Wordnet {specifier!r} cannot be opened: {exc}"
        ) from exc

    loaded = wordnet.lexicons()
    if not loaded:
        raise WordNetError(
            f"Wordnet {specifier!r} is empty -- no lexicon in the database."
        )
    lexicon_id = loaded[0]

    return WordNetResource(
        name=name,
        specifier=lexicon_id.specifier(),
        version=lexicon_id.version,
        license=lexicon_id.license,
        fingerprint=fingerprint,
        size=size if size is not None else len(wordnet.synsets()),
        broader=WordNetHypernyms(wordnet),
        note=note,
        wordnet=wordnet,
    )
