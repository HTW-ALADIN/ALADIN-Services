"""Spec C similarity measures — BERTScore addition.

Adds the `bertscore` tag:
- bert_score.score(cands, refs, model_type, lang, idf, rescale_with_baseline)

Result shape: {"precision": ..., "recall": ..., "f1": ...} — a named-fields
triple rather than a bare scalar (per API spec §6.1).
"""

from typing import Any

from .similarity import DEFAULT_BACKENDS, SIMILARITY_DISPATCH


def _bertscore(input_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import bert_score

    cand = input_data.get("text_a", "")
    ref = input_data.get("text_b", "")
    model_type = params.get("model_type")
    lang = params.get("lang")
    idf = params.get("idf", False)
    rescale_with_baseline = params.get("rescale_with_baseline", False)

    P, R, F1 = bert_score.score(
        [cand],
        [ref],
        model_type=model_type,
        lang=lang,
        idf=idf,
        rescale_with_baseline=rescale_with_baseline,
    )
    return {
        "precision": float(P[0]),
        "recall": float(R[0]),
        "f1": float(F1[0]),
    }


# ─── Register in dispatchers ─────────────────────────────────────────────────

SIMILARITY_DISPATCH.update(
    {
        ("bertscore", "bertscore"): _bertscore,
    }
)

DEFAULT_BACKENDS.update(
    {
        "bertscore": "bertscore",
        # DKPro-sidecar measures: registered as known measures, but the actual
        # computation is routed to the Java sidecar via dkpro_proxy. They are
        # not added to SIMILARITY_DISPATCH (no in-process implementation).
        "topic_model": "dkpro",
        "structural_stylistic": "dkpro",
    }
)
