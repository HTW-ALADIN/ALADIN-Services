'''
Build the lemma list of a language from the wordnet.

    python -m src.mapping.labels.normalization.lang.build_lemmas
    python -m src.mapping.labels.normalization.lang.build_lemmas --dir /elsewhere --lexicon odenet:1.4
    python -m src.mapping.labels.normalization.lang.build_lemmas --out /path/lemmas-de.json

Rewrites src/mapping/labels/normalization/lang/data/lemmas-de.json. Needs the
installed wordnet (python -m src.knowledge.wordnet) and downloads nothing.
The script deliberately does not import the normalization library: that one
loads the list at import, and a script that creates the list must not fail
because it is missing.

Why the list exists
-------------------
The operation ``lemma`` (src/mapping/labels/normalization/ops.py: op_lemma)
reduces a word to its base form by trying out replacements of endings:
"kunden" -> "kunde", "verwaltet" -> "verwalten". Without a set to check
against, that would be stemming under another name -- every rule that fits
would be applied, and "ende" would become "end", "preis" would become "prei".
The list is the set to check against: a candidate only counts if it is a
known word. That is why it is a set and not a table of forms.
src/mapping/labels/semantics/compound.py needs the same set to find the head
of a compound ("rückgabedatum" -> "datum"): the longest tail that is a word.

What goes in
------------
All lemmas of the lexicon, NFC-composed and lower case, namely

  - no multi-word lemmas ("zur Verfügung stellen"): the operations work on
    single words, a multi-word lemma would never hit;
  - nothing below MIN_LEMMA characters: too short to carry an ending, and
    every short word ("ab", "an") would be a collision risk for the rules;
  - only plain words of letters and digits: nothing with a hyphen, dot or
    apostrophe ("e-mail", "z.b.", "d'accord") -- the tokenizing of the
    normalization splits at these characters anyway, a token never contains
    them;
  - every word ADDITIONALLY in folded spelling ("abändern" and "abaendern",
    "café" and "cafe"). In the profile "lemmatized" ``fold`` runs before
    ``lemma``, so the list only sees folded tokens there; the unfolded ones
    stay in so that profiles without ``fold`` (the input profile of the
    semantics) use the same list. Folding follows the same rule as ops.py:
    op_fold -- see UMLAUTS.

Provenance
----------
The header of the file holds the source (lexicon ID, SHA-256 of the LMF file
from the manifest of src/knowledge/wordnet, version of the "wn" library), the
rules (MIN_LEMMA, counts of what was dropped), license and citation.
lang/lexicon.py checks the digest over the list when loading: a file edited
by hand stands out, and the file thus is a derived work with traceable origin.
'''

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

import wn  # noqa: E402

from src.knowledge.wordnet import DATA_DIR, LEXICON, MANIFEST  # noqa: E402

#: lang/lexicon.py is loaded as a file, not as a module of the package -- the
#: package would load the list at import, which does not exist here yet. The
#: digest (must compute identically) and the data path come from there.
LEXICON_PY = Path(__file__).resolve().parent / "lexicon.py"

#: No lemma may be shorter than this.
MIN_LEMMA = 3

#: A word: letters and digits, nothing else -- \w without underscore.
TOKEN = re.compile(r"[^\W_]+")

#: The same table as UMLAUTS in lang/de.py -- as a copy, for the reason given
#: in the module docstring.
UMLAUTS = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
)

LICENSE_NOTE = ("This file is a derived work and is under the same license as "
                "its source. Mind the share-alike terms.")

RULES = ("lemmas NFC + lower case; without multi-word lemmas; at least "
         "min_lemma characters; only letters and digits; every word additionally "
         "umlaut- and diacritic-folded like ops.py: op_fold")


# --------------------------------------------------------------------------- #
# The rules
# --------------------------------------------------------------------------- #

def fold(word):
    '''Write out umlauts, then fold diacritics -- like ops.py: op_fold.'''
    for src, dst in UMLAUTS:
        word = word.replace(src, dst)

    decomposed = unicodedata.normalize("NFKD", word)

    return "".join(c for c in decomposed if not unicodedata.combining(c))


def classify(lemma, min_lemma=MIN_LEMMA):
    '''
    A lemma in its list form -- or the reason why it stays out.

    Returns (word, None) or (None, "multiword" | "short" | "non_token").
    '''
    word = unicodedata.normalize("NFC", lemma).lower()

    if any(c.isspace() for c in word):
        return None, "multiword"

    if len(word) < min_lemma:
        return None, "short"

    if not TOKEN.fullmatch(word):
        return None, "non_token"

    return word, None


def build(lemmas, min_lemma=MIN_LEMMA):
    '''
    The sorted set to check against, from the lemmas of the lexicon -- (entries, counters).

    The counters are per lemma of the lexicon, not per word: a word listed
    under two parts of speech is seen twice and kept once.
    '''
    counters = {"multiword": 0, "short": 0, "non_token": 0}
    base = set()

    for lemma in lemmas:
        word, reason = classify(lemma, min_lemma)

        if reason:
            counters[reason] += 1
        else:
            base.add(word)

    entries = sorted(base | {fold(word) for word in base})
    counters["base_entries"] = len(base)
    counters["folded_added"] = len(entries) - len(base)

    return entries, counters


# --------------------------------------------------------------------------- #
# Source and target
# --------------------------------------------------------------------------- #

def lexicon_module():
    '''lang/lexicon.py as a standalone module -- without loading the package.'''
    spec = importlib.util.spec_from_file_location("build_lemmas.lexicon", LEXICON_PY)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks up the module of a class in sys.modules when the class
    # is created -- a module that is only loaded, not registered, is unknown.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def read_lexicon(directory, specifier):
    '''The installed lexicon and its lemmas -- (lexicon, [lemma]).'''
    # Must be set BEFORE wn touches anything -- otherwise the library creates
    # its database under ~/.wn_data and downloads from the network.
    wn.config.data_directory = str(directory)
    found = wn.lexicons(lexicon=specifier)

    if not found:
        raise SystemExit(
            f"Wordnet {specifier!r} is not installed under {directory}. "
            "Install it with:  python -m src.knowledge.wordnet"
        )

    return found[0], [word.lemma() for word in wn.Wordnet(lexicon=specifier).words()]


def manifest_entry(directory, specifier):
    '''The manifest entry of the lexicon (SHA-256 of the LMF file) -- or {}.'''
    path = Path(directory) / MANIFEST

    if not path.is_file():
        return {}

    return json.loads(path.read_text(encoding="utf-8")).get("lexicons", {}).get(specifier, {})


def meta_for(name, lexicon, lmf, entries, counters, digest, min_lemma=MIN_LEMMA):
    '''The header of the file: what is in it, where it comes from, how it was built.'''
    return {
        "name": name,
        "generator": "src/mapping/labels/normalization/lang/build_lemmas.py",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": len(entries),
        "digest": digest,
        "source": lexicon.specifier(),
        "source_lmf_sha256": lmf.get("lmf_sha256"),
        "label": lexicon.label,
        "license": lexicon.license,
        # From the LMF header, which has line breaks and repeated spaces.
        "citation": " ".join((lexicon.citation or "").split()),
        "url": lexicon.url,
        "license_note": LICENSE_NOTE,
        "wn_version": wn.__version__,
        "rules": RULES,
        "min_lemma": min_lemma,
        "skipped_multiword": counters["multiword"],
        "skipped_short": counters["short"],
        "skipped_non_token": counters["non_token"],
        "base_entries": counters["base_entries"],
        "folded_added": counters["folded_added"],
    }


def write(path, meta, entries):
    '''Write the file -- header first, then the list.'''
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "lemmas": entries}, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")

    return path


def main(argv=None):
    '''Build the list, write it, print the counters.'''
    lexicon_py = lexicon_module()
    parser = argparse.ArgumentParser(prog="python -m src.mapping.labels.normalization.lang.build_lemmas",
                                     description=__doc__.splitlines()[1])
    parser.add_argument("--dir", default=str(DATA_DIR),
                        help=f"directory of the wordnet (default: {DATA_DIR})")
    parser.add_argument("--lexicon", default=LEXICON,
                        help=f"ID id:version (default: {LEXICON})")
    parser.add_argument("--out", default=None,
                        help=f"target file (default: {lexicon_py.DATA_DIR}/lemmas-<language>.json)")
    parser.add_argument("--min-lemma", type=int, default=MIN_LEMMA,
                        help=f"minimum length of a lemma (default: {MIN_LEMMA})")
    args = parser.parse_args(argv)

    directory = Path(args.dir).expanduser()
    lexicon, lemmas = read_lexicon(directory, args.lexicon)
    name = f"lemmas-{lexicon.language}"
    out = Path(args.out).expanduser() if args.out else lexicon_py.DATA_DIR / f"{name}.json"

    entries, counters = build(lemmas, args.min_lemma)
    digest = lexicon_py._digest(entries)
    meta = meta_for(name, lexicon, manifest_entry(directory, args.lexicon),
                    entries, counters, digest, args.min_lemma)
    path = write(out, meta, entries)

    print(f"Lemma list {name} from {meta['source']} ({len(lemmas)} lemmas)")
    print(f"  dropped: {counters['multiword']} multi-word, {counters['short']} short, "
          f"{counters['non_token']} not a word")
    print(f"  kept: {counters['base_entries']} words + {counters['folded_added']} folded "
          f"= {len(entries)} entries")
    print(f"  {digest[:23]}...")
    print(f"  -> {path}")


if __name__ == "__main__":
    main()
