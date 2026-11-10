"""Build-time helper: download HuggingFace models onto the image disk.

Used so a container built with ``HF_PRELOAD=all`` (or a partial
``measure:model,...`` select) serves its first model request OFFLINE: instead of a
runtime spend to HuggingFace Hub, the weights are already present on disk.

It mirrors the runtime HF cache layout ($BUILT_HF / $HF_HOME) so
sentence-transformers/transformers find the weights in a fresh container with
no extra migration. It downloads weights but does NOT load them into RAM.

The selection is driven by the same ``HF_PRELOAD`` build-arg as the runtime
warm-start (see src/model_cache.py): ``off`` (default) does nothing here;
``all`` / ``measure:model,...`` pre-downloads exactly the models that the
warm-start would otherwise warm. A build failure (e.g. offline farm) must never
break the build — models simply stay lazy-downloadable at runtime.

Called from the Dockerfile as ``RUN PYTHONDONTWRITEBYTECODE=1 python src/__precache_hf.py``.
"""

import os

from src import model_cache as mc


def _download_model(measure: str, model_name: str) -> list[str]:
    """Download one model's weights to the HF disk cache; return labels logged.

    Dispatches on the measure to the class that materialises the correct
    on-disk layout (SentenceTransformer / CrossEncoder / AutoModel+Tokenizer).
    The network is only touched here; nothing is imported into memory for
    serving.
    """
    from sentence_transformers import CrossEncoder, SentenceTransformer
    from transformers import AutoModel, AutoTokenizer

    if measure in ("sbert_cosine", "semantic_search"):
        SentenceTransformer(f"sentence-transformers/{model_name}")
        return [f"sbert_cosine({model_name})"]
    if measure == "cross_encoder":
        CrossEncoder(f"cross-encoder/{model_name}")
        return [f"cross_encoder({model_name})"]
    if measure == "bertscore":
        AutoModel.from_pretrained(model_name)
        AutoTokenizer.from_pretrained(model_name)
        return [f"bertscore({model_name})"]
    raise ValueError(f"no downloader for measure {measure!r}")


def main() -> None:
    spec = os.environ.get(mc.HF_PRELOAD_ENV, "").strip()
    if spec.lower() in ("", "off", "none", "false", "0"):
        print("HF_PRELOAD=off — skipping HuggingFace disk pre-cache.")
        return

    errors = 0
    for measure, model_name in mc._preload_entries(spec):
        try:
            labels = _download_model(measure, model_name)
            print(f"pre-cached to disk: {', '.join(labels)}", flush=True)
        except Exception as exc:  # noqa: BLE001  # never fail the image build
            errors += 1
            print(f"WARN: pre-cache failed for {measure}({model_name}): {exc}", flush=True)
    if errors:
        print(f"{errors} model(s) failed to pre-cache; they will download lazily at runtime.")
    else:
        print("HuggingFace disk pre-cache done.")


if __name__ == "__main__":
    # Guard against accidental top-level import in the running service (lazy
    # loading must stay intact): the heavy libs are only imported inside
    # _download_model, and _preload_entries is exercised at build time only.
    main()
