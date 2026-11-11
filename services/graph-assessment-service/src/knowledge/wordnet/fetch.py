'''
Fetch the wordnet -- a build step and not a runtime path.

    python -m src.knowledge.wordnet
    python -m src.knowledge.wordnet --dir /elsewhere --lexicon odenet:1.4

Creates the wordnet database under DATA_DIR (src/knowledge/wordnet/data/, or
whatever $SEMANTICS_WN_DATA says) and writes a manifest next to it. Calling
it twice does no harm: what is already installed is not loaded again.

Fetching happens before the run and not in it. Without a data directory set,
the library "wn" downloads from the network on first access -- right in the
middle of a comparison, and a run that fetches data along the way is not
repeatable.

The manifest holds the SHA-256 over the downloaded LMF file. That way the
fingerprint of the resource is over the DATA and not over its name.
'''

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import wn

from . import DATA_DIR, LEXICON, MANIFEST


def sha256(path):
    '''SHA-256 over a file, in chunks -- the LMF file is large.'''
    hasher = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)

    return hasher.hexdigest()


def fetch(directory, lexicon):
    '''
    Download, install, build the manifest entry.

    Separate steps so that a second call breaks nothing: the download lands
    in a cache, the installation only happens if the lexicon is not yet in
    the database. A "wn.add" on an existing lexicon would be an error.
    '''
    directory.mkdir(parents=True, exist_ok=True)
    # Must be set BEFORE wn touches anything -- otherwise the library creates
    # its database under ~/.wn_data, as a side effect.
    wn.config.data_directory = str(directory)

    lmf = wn.download(lexicon, add=False)

    if wn.lexicons(lexicon=lexicon):
        print(f"  {lexicon} is already in the database -- not installed again.")
    else:
        wn.add(lmf)

    loaded = wn.lexicons(lexicon=lexicon)[0]

    return loaded.specifier(), {
        "lmf_file": Path(lmf).name,
        "lmf_sha256": sha256(lmf),
        "synsets": len(wn.Wordnet(lexicon=lexicon).synsets()),
        "version": loaded.version,
        "license": loaded.license,
        "fetched": date.today().isoformat(),
    }


def write_manifest(directory, specifier, entry):
    '''
    Put the entry into the manifest -- without losing the others.

    Read and written back instead of overwritten, so that a second lexicon in
    the same directory does not forget the first.
    '''
    path = directory / MANIFEST
    data = {}

    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))

    data.setdefault("lexicons", {})[specifier] = entry
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

    return path


def main():
    '''Fetch the wordnet and write the manifest.'''
    parser = argparse.ArgumentParser(prog="python -m src.knowledge.wordnet",
                                     description=__doc__.splitlines()[1])
    parser.add_argument("--dir", default=str(DATA_DIR),
                        help=f"target directory (default: {DATA_DIR})")
    parser.add_argument("--lexicon", default=LEXICON,
                        help=f"ID id:version (default: {LEXICON})")
    args = parser.parse_args()
    directory = Path(args.dir).expanduser()

    print(f"Wordnet {args.lexicon} -> {directory}")
    specifier, entry = fetch(directory, args.lexicon)
    path = write_manifest(directory, specifier, entry)

    print(f"  {specifier}: {entry['synsets']} synsets, "
          f"license {entry['license']}")
    print(f"  sha256:{entry['lmf_sha256'][:16]} over {entry['lmf_file']}")
    print(f"  Manifest: {path}")
    print()
    print("The wordnet stages in src/mapping/labels/label_match.py are ready now.")


if __name__ == "__main__":
    main()
