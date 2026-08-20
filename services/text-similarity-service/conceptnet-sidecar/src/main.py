"""FastAPI application for the ConceptNet Numberbatch sidecar.

Serves the local gensim KeyedVectors model over HTTP so the main
text-similarity-service can use ``embedding_cosine`` / ``conceptnet_numberbatch`` /
``backend: local`` without loading the ~3-6 GB model in its own process.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool

from . import model_cache
from .model_cache import ModelFileError
from .models import RelatednessItem, RelatednessRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)

# Numberbatch keys are ConceptNet URIs (/c/{lang}/{term}); the load path also
# receives bare terms and multi-token phrases (the main service always normalizes
# to /c/{lang}/{term} URIs before calling us).
_DEFAULT_LANG = "en"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    model_cache._load_sync()
    task = __import__("asyncio").create_task(model_cache.eviction_loop())
    yield
    task.cancel()


app = FastAPI(title="conceptnet-sidecar", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    """Liveness: the process is up. Independent of the model load state."""
    return {"status": "ok", "service": "conceptnet-sidecar"}


@app.get("/health/ready")
def ready():
    """Readiness: the sidecar can serve relatedness.

    200 if the model is loaded OR would lazy-load on demand; 503 only on a real
    error (e.g. the model file is missing or not set).
    """
    try:
        if not model_cache.MODEL_PATH or not __import__("os").path.exists(model_cache.MODEL_PATH):
            raise ModelFileError("CONCEPTNET_MODEL_PATH not set or missing")
    except Exception:  # noqa: BLE001 - rootfs IO error
        raise HTTPException(status_code=503, detail="ConceptNet model unavailable") from None
    if model_cache.cache.status()["model_loaded"] or model_cache.PRELOAD_ON_START:
        return {"status": "ready", "service": "conceptnet-sidecar", "model": "loaded"}
    # Model not yet loaded but lazy-loadable — still ready.
    return {"status": "ready", "service": "conceptnet-sidecar", "model": "lazy"}


@app.get("/v1/status")
def status():
    return model_cache.cache.status()


@app.post("/v1/relatedness")
async def relatedness(request: RelatednessRequest):
    """Score a batch of word pairs using gensim ``KeyedVectors.similarity``.

    Returns one item per pair. Out-of-vocabulary words yield ``score: null`` with
    an ``error`` message for that pair instead of failing the whole batch. Scores
    are raw cosine similarity in ``[-1, 1]`` — normalization to ``[0,1]`` is the
    main service's job so this sidecar stays dumb and replaceable.
    """
    try:
        kv = await run_in_threadpool(model_cache.cache.get_model)
    except ModelFileError as e:
        # Never leak the internal model filesystem path (CONCEPTNET_MODEL_PATH) in
        # the response body; log the real error server-side for operators instead.
        logger.error("conceptnet model load failed: %s", e)
        raise HTTPException(status_code=503, detail="ConceptNet model unavailable") from None

    items: list[RelatednessItem] = []
    for pair in request.pairs:
        items.append(_score_pair(kv, pair.id, pair.word_a, pair.word_b, pair.lang))
    return items


def _score_pair(kv, pair_id: str, word_a: str, word_b: str, lang: str) -> RelatednessItem:
    uri_a = _to_uri(word_a, lang)
    uri_b = _to_uri(word_b, lang)
    # Match the REMOTE backend's empty/meaningless-term behavior (see
    # conceptnet_api.to_conceptnet_uri / the URI parity review): the term is the
    # segment after the final '/c/{lang}/' component.
    term_a = uri_a.rsplit("/", 1)[-1]
    term_b = uri_b.rsplit("/", 1)[-1]
    if not term_a and not term_b:
        return RelatednessItem(id=pair_id, score=1.0)  # both sides empty -> identical
    if not term_a or not term_b:
        return RelatednessItem(id=pair_id, score=0.0)  # exactly one empty -> nothing in common
    try:
        if uri_a == uri_b:
            score = 1.0
        else:
            score = float(kv.similarity(uri_a, uri_b))
        return RelatednessItem(id=pair_id, score=round(score, 4))
    except KeyError as e:
        missing = str(e).strip("'\"")
        return RelatednessItem(id=pair_id, error=f"oov: {missing}")


def _to_uri(term: str, lang: str) -> str:
    """Normalize a term to a ConceptNet /c/{lang}/{term} URI (spaces -> underscores)."""
    import re

    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", "_".join(term.split())).strip("_")
    return f"/c/{lang}/{normalized}" if normalized else ""
