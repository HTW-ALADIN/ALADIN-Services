"""Tests for the ``HF_PRELOAD`` preload-profile parsing.

Covers the three build-time modes (off / all / partial) plus invalid-entry
handling, and the reusable ``_preload_entries`` that drives both the disk
pre-cache and the RAM warm-start. Pure parsing only — no torch /
sentence-transformers import is triggered here.
"""

import pytest
from src import model_cache as mc


def _all_models() -> list[tuple[str, str]]:
    return [(m, n) for m, names in mc._DFLT_PRELOAD_HF.items() for n in names]


@pytest.fixture(autouse=True)
def _clean_preload_env(monkeypatch):
    monkeypatch.delenv(mc.HF_PRELOAD_ENV, raising=False)


def _spec(value: str):
    return mc._preload_entries(value)


def test_off_yields_empty(monkeypatch):
    for value in ("off", "none", "false", "0", ""):
        assert _spec(value) == []


@pytest.mark.parametrize("value", ["all", "true", "1", "ALL"])
def test_all_yields_every_advertised_model(value):
    assert _spec(value) == _all_models()


def test_partial_selects_only_the_given_models():
    spec = _spec("sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large")
    assert spec == [
        ("sbert_cosine", "all-MiniLM-L6-v2"),
        ("bertscore", "roberta-large"),
    ]


def test_partial_semantic_search_alias():
    assert _spec("semantic_search:all-mpnet-base-v2") == [("semantic_search", "all-mpnet-base-v2")]


def test_unknown_measure_and_model_are_skipped(caplog):
    spec = _spec("foo:bar,sbert_cosine:not-a-model,cross_encoder:stsb-roberta-base")
    assert spec == [("cross_encoder", "stsb-roberta-base")]
    assert any("unknown measure" in r.message for r in caplog.records)
    assert any("not on the allow-list" in r.message for r in caplog.records)


def test_malformed_entry_is_ignored(caplog):
    assert _spec("sbert_cosine:all-MiniLM-L6-v2,garbage") == [("sbert_cosine", "all-MiniLM-L6-v2")]
    assert any("malformed" in r.message for r in caplog.records)


def test_is_warm_reflects_profile(monkeypatch):
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "all")
    assert mc.is_warm() is True
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "sbert_cosine:all-MiniLM-L6-v2")
    assert mc.is_warm() is True
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "off")
    assert mc.is_warm() is False
