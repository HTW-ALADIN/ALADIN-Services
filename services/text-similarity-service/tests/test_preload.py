"""Tests for the ``HF_PRELOAD`` warm-start preload profile parsing.

Covers the three build-time profiles (off / all / partial) plus the legacy
``HF_MODELS_PRELOAD`` synonym and invalid-enttry handling. Pure parsing only —
no torch / sentence-transformers import is triggered here.
"""

import pytest
from src import model_cache as mc


@pytest.fixture(autouse=True)
def _clean_preload_env(monkeypatch):
    monkeypatch.delenv(mc.HF_PRELOAD_ENV, raising=False)
    monkeypatch.delenv(mc._LEGACY_PRELOAD_ENV, raising=False)


def _spec(monkeypatch, value):
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, value)
    return mc._parse_preload_spec()


def test_off_yields_empty(monkeypatch):
    for value in ("off", "none", "false", "0", ""):
        assert _spec(monkeypatch, value) == []


@pytest.mark.parametrize("value", ["all", "true", "1", "ALL"])
def test_all_yields_every_advertised_model(monkeypatch, value):
    spec = _spec(monkeypatch, value)
    assert spec == list(mc._DFLT_PRELOAD_HF)


def test_partial_selects_only_the_given_models(monkeypatch):
    spec = _spec(monkeypatch, "sbert_cosine:all-MiniLM-L6-v2,bertscore:roberta-large")
    assert spec == [
        ("sbert_cosine", "all-MiniLM-L6-v2"),
        ("bertscore", "roberta-large"),
    ]


def test_partial_semantic_search_alias(monkeypatch):
    spec = _spec(monkeypatch, "semantic_search:all-mpnet-base-v2")
    assert spec == [("semantic_search", "all-mpnet-base-v2")]


def test_unknown_measure_and_model_are_skipped(monkeypatch, caplog):
    spec = _spec(
        monkeypatch,
        "foo:bar,sbert_cosine:not-a-model,cross_encoder:stsb-roberta-base",
    )
    assert spec == [("cross_encoder", "stsb-roberta-base")]
    assert any("unknown measure" in r.message for r in caplog.records)
    assert any("not on the allow-list" in r.message for r in caplog.records)


def test_malformed_entry_is_ignored(monkeypatch, caplog):
    spec = _spec(monkeypatch, "sbert_cosine:all-MiniLM-L6-v2,garbage")
    assert spec == [("sbert_cosine", "all-MiniLM-L6-v2")]
    assert any("malformed" in r.message for r in caplog.records)


def test_legacy_hf_models_preload_is_synonym_for_all(monkeypatch):
    monkeypatch.setenv(mc._LEGACY_PRELOAD_ENV, "true")
    assert mc._parse_preload_spec() == list(mc._DFLT_PRELOAD_HF)


def test_legacy_flag_off_with_false_preload(monkeypatch):
    monkeypatch.setenv(mc._LEGACY_PRELOAD_ENV, "false")
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "off")
    assert mc._parse_preload_spec() == []


def test_is_warm_reflects_profile(monkeypatch):
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "all")
    assert mc.is_warm() is True
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "sbert_cosine:all-MiniLM-L6-v2")
    assert mc.is_warm() is True
    monkeypatch.setenv(mc.HF_PRELOAD_ENV, "off")
    assert mc.is_warm() is False
