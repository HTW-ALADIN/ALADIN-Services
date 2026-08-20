"""Build-time helper: download HuggingFace models used by the service.

Runs only when ``PRECACHE_HF`` environment variable equals "true" (set via the
Dockerfile build arg). It mirrors the runtime HF cache layout ($BUILT_HF /
$HF_HOME) so sentence-transformers/transformers find the weights in a fresh
container with no extra migration. It downloads weights but does NOT load them
into RAM — index files/blobs go straight to disk cache.

Called from the Dockerfile as ``RUN PYTHONDONTWRITEBYTECODE=1 python src/__precache_hf.py``.
"""

import os


def main() -> None:
    if os.environ.get("PRECACHE_HF", "").lower() not in ("1", "true", "yes"):
        print("PRECACHE_HF not enabled — skipping HuggingFace pre-cache.")
        return

    from sentence_transformers import CrossEncoder, SentenceTransformer
    from transformers import AutoModel, AutoTokenizer

    names = (
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-mpnet-base-v2",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "cross-encoder/stsb-roberta-base",
        "roberta-large",
    )
    for n in names:
        print(f"pre-caching {n} ...", flush=True)
    SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
    SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    CrossEncoder("cross-encoder/stsb-roberta-base")
    AutoModel.from_pretrained("roberta-large")
    AutoTokenizer.from_pretrained("roberta-large")
    print("HuggingFace pre-cache done.")


if __name__ == "__main__":
    # Guard against accidental top-level import in the running service (lazy
    # loading must stay intact): __name__ == module name in the service, and the
    # heavy libs are only imported here when executed as a script.
    main()
