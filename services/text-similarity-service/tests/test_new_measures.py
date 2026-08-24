"""Tests for the incremental extensions.

Covers the CPU-only measures (token_set_overlap with jaccard/dice variants and
the legacy jaccard/dice aliases, bm25), the configurable static embedding
variants (glove / fasttext / conceptnet_numberbatch), the German Odenet lexical
backend, and the parametrizable SBERT model_name. Model downloads are avoided
by monkeypatching the model cache.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from src.lexical import compute_lexical
from src.main import app
from src.model_cache import LargeModelDownloadBlocked, clear_all
from src.retrieval import compute_retrieval
from src.similarity import compute_similarity

client = TestClient(app)


class TestTokenSetOverlap:
    """Canonical token_set_overlap algorithm with params.variant."""

    def test_jaccard_variant_identical(self):
        r = compute_similarity(
            "token_set_overlap", "builtin", {"text_a": "the cat is here", "text_b": "the cat is here"}, {"variant": "jaccard"}
        )
        assert r["similarity"] == 1.0

    def test_jaccard_variant_disjoint(self):
        r = compute_similarity("token_set_overlap", "builtin", {"text_a": "alpha beta", "text_b": "gamma delta"}, {"variant": "jaccard"})
        assert r["similarity"] == 0.0

    def test_jaccard_variant_partial_overlap(self):
        # {the, cat, is, here} vs {the, cat, is, there}: 3/5
        r = compute_similarity(
            "token_set_overlap", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {"variant": "jaccard"}
        )
        assert r["similarity"] == pytest.approx(3 / 5)

    def test_dice_variant_partial_overlap(self):
        # 2|A∩B|/(|A|+|B|) = 2*3/(4+4) = 0.75
        r = compute_similarity(
            "token_set_overlap", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {"variant": "dice"}
        )
        assert r["similarity"] == pytest.approx(0.75)

    def test_default_variant_is_jaccard(self):
        r = compute_similarity("token_set_overlap", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {})
        assert r["similarity"] == pytest.approx(3 / 5)

    def test_dice_is_monotone_transform_of_jaccard(self):
        """dice = 2*jaccard / (1+jaccard) — same ranking, different scale."""
        j = compute_similarity(
            "token_set_overlap", "builtin", {"text_a": "alpha beta gamma", "text_b": "alpha beta delta"}, {"variant": "jaccard"}
        )["similarity"]
        d = compute_similarity(
            "token_set_overlap", "builtin", {"text_a": "alpha beta gamma", "text_b": "alpha beta delta"}, {"variant": "dice"}
        )["similarity"]
        assert d == pytest.approx(2 * j / (1 + j))

    def test_empty_inputs(self):
        assert compute_similarity("token_set_overlap", "builtin", {"text_a": "", "text_b": ""}, {})["similarity"] == 1.0
        assert compute_similarity("token_set_overlap", "builtin", {"text_a": "", "text_b": "x"}, {})["similarity"] == 0.0

    def test_api_canonical(self):
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "token_set_overlap",
                "params": {"variant": "dice"},
                "inputs": [{"id": "p1", "a": "the cat is here", "b": "the cat is there"}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "builtin"
        assert body["results"][0]["result"]["similarity"] == pytest.approx(0.75)


class TestTokenSetAliases:
    """Legacy 'jaccard' / 'dice' algorithm names stay valid and are fixed-variant."""

    def test_jaccard_alias(self):
        r = compute_similarity("jaccard", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {})
        assert r["similarity"] == pytest.approx(3 / 5)

    def test_jaccard_alias_disjoint(self):
        r = compute_similarity("jaccard", "builtin", {"text_a": "alpha beta", "text_b": "gamma delta"}, {})
        assert r["similarity"] == 0.0

    def test_jaccard_alias_ignores_contrary_variant(self):
        """The alias pins the variant — even a dice request maps to jaccard."""
        r = compute_similarity("jaccard", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {"variant": "dice"})
        assert r["similarity"] == pytest.approx(3 / 5)

    def test_dice_alias(self):
        r = compute_similarity("dice", "builtin", {"text_a": "the cat is here", "text_b": "the cat is there"}, {})
        assert r["similarity"] == pytest.approx(0.75)

    def test_dice_alias_empty(self):
        assert compute_similarity("dice", "builtin", {"text_a": "", "text_b": ""}, {})["similarity"] == 1.0
        assert compute_similarity("dice", "builtin", {"text_a": "", "text_b": "y"}, {})["similarity"] == 0.0

    def test_api_jaccard_alias(self):
        """Alias requests echo the requested algorithm name in the response."""
        resp = client.post(
            "/v1/similarity/text/distance",
            json={"algorithm": "jaccard", "params": {}, "inputs": [{"id": "p1", "a": "the cat is here", "b": "the cat is there"}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "jaccard"
        assert body["backend"] == "builtin"
        assert body["results"][0]["result"]["similarity"] == pytest.approx(3 / 5)


class TestBM25:
    def test_obvious_hit_ranks_higher(self):
        r = compute_retrieval(
            "bm25",
            "builtin",
            {"query": "the cat sat", "candidates": ["the cat sat on the mat", "quantum physics theory"]},
            {},
        )
        assert r["count"] == 2
        assert r["matches"][0]["corpus_id"] == 0

    def test_multiple_candidates(self):
        r = compute_retrieval(
            "bm25",
            "builtin",
            {"query": "cat", "candidates": ["a cat", "a dog", "a cat and a dog", "house"]},
            {"top_k": 3},
        )
        assert len(r["matches"]) <= 3
        assert r["matches"][0]["candidate"] == "a cat"

    def test_empty_candidates(self):
        r = compute_retrieval("bm25", "builtin", {"query": "cat", "candidates": []}, {})
        assert r["matches"] == []
        assert r["count"] == 0

    def test_api_batch(self):
        resp = client.post(
            "/v1/similarity/text/retrieval",
            json={
                "algorithm": "bm25",
                "params": {},
                "inputs": [
                    {"id": "q1", "query": "cat", "candidates": ["a cat", "a dog"]},
                    {"id": "q2", "query": "car", "candidates": ["car repair", "bank loan"]},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "builtin"
        assert [r["id"] for r in body["results"]] == ["q1", "q2"]


class FakeKeyedVectors:
    """Minimal stand-in for a gensim KeyedVectors (avoids model downloads)."""

    key_to_index = {
        "/c/en/car": 0,
        "/c/en/auto": 1,
        "/c/en/cat": 2,
    }

    def __init__(self, dim=4):
        self._dim = dim

    def similarity(self, a, b):
        return 0.9 if a == b else 0.4

    def n_similarity(self, a, b):
        return 0.7


class TestEmbeddingVariants:
    def test_variant_selects_model(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "fasttext", "confirm_large_download": True}
        )
        assert captured == ["fasttext-wiki-news-subwords-300"]

    def test_conceptnet_variant(self, monkeypatch):
        """Sidecar path for conceptnet_numberbatch (the default backend).

        ``params.backend`` defaults to ``"local"`` for this variant — it is
        served by the ConceptNet sidecar (see tests/test_conceptnet_remote.py),
        NOT loaded as an in-process gensim model.
        """
        captured: list[str] = []

        def fake_get_relatedness(pairs):
            captured.append(pairs[0]["word_a"])
            return [{"id": pairs[0]["id"], "score": 0.4, "error": None}]

        monkeypatch.setattr("src.conceptnet_client.get_relatedness", fake_get_relatedness)
        compute_similarity(
            "embedding_cosine",
            "gensim",
            {"text_a": "car", "text_b": "auto"},
            {"variant": "conceptnet_numberbatch", "backend": "local", "confirm_large_download": True},
        )
        assert captured == ["car"]

    def test_default_is_glove(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {})
        assert captured == ["glove-wiki-gigaword-50"]

    def test_explicit_model_name_wins(self, monkeypatch):
        """An explicit params.model_name overrides the default model.

        The chosen name is patched to resolve as *small* (below the cost gate)
        so the test stays deterministic and offline; only the
        "explicit name wins over the default" behavior is under test here.
        """
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        # A small, gate-free explicit model (kept deterministic, no network).
        monkeypatch.setattr("src.model_cache._resolve_download_size_mb", lambda name: 50, raising=False)
        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"model_name": "some-small-custom-model"})
        assert captured == ["some-small-custom-model"]

    def test_explicit_large_model_requires_opt_in(self, monkeypatch):
        """A large explicit params.model_name still hits the cost gate.

        Regression for the old behavior where the gensim-metadata lookup could
        silently resolve to 0 MB and let a multi-GB model_name download without
        an opt-in (a >500 MB runtime download slipped past the gate).
        """

        def fake_get(name):
            raise AssertionError("model should not be downloaded without opt-in")

        monkeypatch.setattr("src.model_cache._resolve_download_size_mb", lambda name: 1600, raising=False)
        monkeypatch.setattr("src.model_cache._gensim_model_on_disk", lambda name: False, raising=False)
        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        with pytest.raises(LargeModelDownloadBlocked):
            compute_similarity(
                "embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"model_name": "word2vec-google-news-300"}
            )

        # With the opt-in the download proceeds.
        imported: list[str] = []

        def fake_get_ok(name):
            imported.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get_ok)
        clear_all()
        compute_similarity(
            "embedding_cosine",
            "gensim",
            {"text_a": "car", "text_b": "auto"},
            {"model_name": "word2vec-google-news-300", "confirm_large_download": True},
        )
        assert imported == ["word2vec-google-news-300"]

    def test_cache_is_used(self, monkeypatch):
        """The real get_gensim_model cache downloads a model only once."""
        calls = {"n": 0}

        def fake_load(name, **kw):
            calls["n"] += 1
            return FakeKeyedVectors()

        monkeypatch.setattr("gensim.downloader.load", fake_load)
        clear_all()
        compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "a", "text_b": "b"}, {"variant": "fasttext", "confirm_large_download": True}
        )
        compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "a", "text_b": "b"}, {"variant": "fasttext", "confirm_large_download": True}
        )
        assert calls["n"] == 1  # model loaded once, cached


class TestCostGate:
    """Large-download cost gate for embedding_cosine (fasttext / conceptnet local).

    Downloads above the 500 MB threshold need an explicit opt-in BEFORE the
    first download: ``params.confirm_large_download: true`` or the env var
    ``ALLOW_LARGE_MODEL_DOWNLOADS=true``. Small models (glove) and already
    cached models pass without opt-in.
    """

    FASTTEXT = "fasttext-wiki-news-subwords-300"

    def test_fasttext_blocked_without_opt_in(self, monkeypatch):
        # Force "not on disk" so the test passes deterministically even on a
        # dev machine that already downloaded fasttext into the gensim data dir.
        monkeypatch.setattr("src.model_cache._gensim_model_on_disk", lambda name: False)
        clear_all()
        with pytest.raises(LargeModelDownloadBlocked):
            compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "fasttext"})

    def test_fasttext_allowed_with_request_param(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        compute_similarity(
            "embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "fasttext", "confirm_large_download": True}
        )
        assert captured == [self.FASTTEXT]

    def test_fasttext_allowed_with_env_var(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        monkeypatch.setenv("ALLOW_LARGE_MODEL_DOWNLOADS", "true")
        clear_all()
        compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "fasttext"})
        assert captured == [self.FASTTEXT]

    def test_cached_large_model_needs_no_opt_in(self, monkeypatch):
        """A second call (model already cached) runs normally without opt-in."""
        from src import model_cache

        def fake_get(name):
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        model_cache._models[f"gensim:{self.FASTTEXT}"] = FakeKeyedVectors()
        try:
            r = compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {"variant": "fasttext"})
            assert r["similarity"] == 0.4
        finally:
            clear_all()

    def test_conceptnet_local_bypasses_in_process_gate(self, monkeypatch):
        """The conceptnet local path no longer downloads/loads the model in-process.

        It is served by the ConceptNet sidecar (see ADR-0001), so the in-process
        gensim cost gate must not engage — the sidecar owns the model's life.
        """
        monkeypatch.setattr(
            "src.model_cache.get_gensim_model",
            lambda name: (_ for _ in ()).throw(AssertionError("conceptnet must not load a gensim model in-process")),
        )
        captured: list[dict] = []

        def fake_get_relatedness(pairs):
            captured.append(pairs)
            return [{"id": pairs[0]["id"], "score": 0.4, "error": None}]

        monkeypatch.setattr("src.conceptnet_client.get_relatedness", fake_get_relatedness)
        # No opt-in is needed and no in-process model is touched.
        result = compute_similarity(
            "embedding_cosine",
            "gensim",
            {"text_a": "car", "text_b": "auto"},
            {"variant": "conceptnet_numberbatch", "backend": "local"},
        )
        assert captured, "should have routed to the sidecar"
        assert result["similarity"] == 0.4

    def test_glove_default_needs_no_opt_in(self, monkeypatch):
        """The default variant (glove, ~200 MB) is automatic — no gate."""
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        compute_similarity("embedding_cosine", "gensim", {"text_a": "car", "text_b": "auto"}, {})
        assert captured == ["glove-wiki-gigaword-50"]

    def test_api_blocked_returns_400_problem_json(self):
        clear_all()
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "embedding_cosine",
                "params": {"variant": "fasttext"},
                "inputs": [{"id": "p1", "a": "car", "b": "auto"}],
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "2048" in body["detail"]  # exact download size
        assert "confirm_large_download" in body["detail"]  # per-request opt-in
        assert "ALLOW_LARGE_MODEL_DOWNLOADS" in body["detail"]  # server-side opt-in

    def test_api_allowed_with_opt_in(self, monkeypatch):
        captured: list[str] = []

        def fake_get(name):
            captured.append(name)
            return FakeKeyedVectors()

        monkeypatch.setattr("src.model_cache.get_gensim_model", fake_get)
        clear_all()
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "embedding_cosine",
                "params": {"variant": "fasttext", "confirm_large_download": True},
                "inputs": [{"id": "p1", "a": "car", "b": "auto"}],
            },
        )
        assert resp.status_code == 200
        assert captured == [self.FASTTEXT]


class TestOdenet:
    def test_missing_wn_returns_501(self):
        """Without the optional 'de' extra, odenet requests return a clean 501."""
        try:
            import wn  # noqa: F401

            pytest.skip("wn installed — 501 path not applicable here")
        except ImportError:
            pass
        resp = client.post(
            "/v1/similarity/text/lexical",
            json={"algorithm": "synonym", "backend": "odenet", "params": {}, "inputs": [{"id": "w1", "word": "Hund"}]},
        )
        assert resp.status_code == 501
        assert ".[de]" in resp.json()["detail"]


class TestOdenetRelations:
    """Real-data tests — skipped unless the 'de' extra (wn) + Odenet data exist."""

    @classmethod
    def setup_class(cls):
        pytest.importorskip("wn")
        try:
            from src.model_cache import get_odenet

            get_odenet()
        except Exception:  # noqa: BLE001  (no data / no network)
            pytest.skip("Odenet data not available")

    def test_synonym(self):
        r = compute_lexical("synonym", "odenet", {"word": "Auto"}, {})
        assert r["count"] > 0
        assert r["resource"] == "odenet:1.4"

    def test_hypernym(self):
        r = compute_lexical("hypernym", "odenet", {"word": "Hund"}, {})
        assert r["count"] > 0

    def test_hyponym(self):
        r = compute_lexical("hyponym", "odenet", {"word": "Hund"}, {})
        assert r["count"] > 0

    def test_antonym_when_data_present(self):
        r = compute_lexical("antonym", "odenet", {"word": "voll"}, {})
        assert r["count"] > 0

    def test_missing_word_is_graceful(self):
        r = compute_lexical("synonym", "odenet", {"word": "xyzzyplugh"}, {})
        assert r["count"] == 0


class TestSbertModelName:
    @pytest.fixture(autouse=True)
    def _require_sentence_transformers(self):
        """Skips when the optional [model] extra (PyTorch) is not installed."""
        pytest.importorskip("sentence_transformers")

    def test_default_model_name(self, monkeypatch):
        captured: list[str] = []

        class FakeModel:
            def encode(self, texts, **kw):
                return np.array([[1.0, 0.0], [1.0, 0.0]])

        def fake_get(name):
            captured.append(name)
            return FakeModel()

        monkeypatch.setattr("src.model_cache.get_sbert_model", fake_get)
        clear_all()
        r = compute_similarity("sbert_cosine", "sentence_transformers", {"text_a": "a", "text_b": "b"}, {})
        assert captured == ["all-MiniLM-L6-v2"]
        assert r["similarity"] == pytest.approx(1.0)

    def test_custom_model_name(self, monkeypatch):
        captured: list[str] = []

        class FakeModel:
            def encode(self, texts, **kw):
                return np.array([[1.0, 0.0], [0.0, 1.0]])

        def fake_get(name):
            captured.append(name)
            return FakeModel()

        monkeypatch.setattr("src.model_cache.get_sbert_model", fake_get)
        clear_all()
        r = compute_similarity(
            "sbert_cosine", "sentence_transformers", {"text_a": "a", "text_b": "b"}, {"model_name": "paraphrase-multilingual-MiniLM-L12-v2"}
        )
        assert captured == ["paraphrase-multilingual-MiniLM-L12-v2"]
        assert r["similarity"] == pytest.approx(0.0)


class TestHfModelAllowlist:
    """HF weight loading is restricted to a curated allow-list (#1).

    These do NOT need the optional [model] extra: the allow-list check runs
    before any model import/load, so (a) rejected names raise a clean 400 and
    (b) accepted names can be verified against a mocked model loader.
    """

    def test_direct_allowlist_default_sbert(self):
        from src.model_cache import require_allowed_model

        require_allowed_model("sbert_cosine", "all-MiniLM-L6-v2")  # default — ok
        require_allowed_model("sbert_cosine", None)  # None -> built-in default

    def test_allowlist_is_org_prefix_tolerant(self):
        from src.model_cache import require_allowed_model

        require_allowed_model("sbert_cosine", "sentence-transformers/all-MiniLM-L6-v2")
        require_allowed_model("cross_encoder", "cross-encoder/stsb-roberta-base")
        require_allowed_model("bertscore", "roberta-large")

    def test_disallowed_model_rejected(self):
        from src.model_cache import require_allowed_model

        with pytest.raises(ValueError, match="not on the allow-list"):
            require_allowed_model("sbert_cosine", "some-arbitrary-hf-model")
        with pytest.raises(ValueError, match="not on the allow-list"):
            require_allowed_model("cross_encoder", "facebook/bart-large")
        with pytest.raises(ValueError, match="not on the allow-list"):
            require_allowed_model("bertscore", "microsoft/deberta-v3-large")

    def test_unknown_measure_fails_loud(self):
        from src.model_cache import require_allowed_model

        with pytest.raises(ValueError, match="not an HF model-backed measure"):
            require_allowed_model("nonsense_measure", "x")

    @pytest.mark.model
    def test_sbert_cosine_accepts_allowlisted_model(self, monkeypatch):
        # Requires the optional [model] extra: the accepted path calls the real
        # sentence_transformers.util.cos_sim, so it cannot run in the base
        # (no-model) test job. Deselected there via the `model` marker.
        captured: list[str] = []

        class FakeModel:
            def encode(self, texts, **kw):
                return np.array([[1.0, 0.0], [1.0, 0.0]])

        monkeypatch.setattr("src.model_cache.get_sbert_model", lambda name: (captured.append(name), FakeModel())[1])
        clear_all()
        r = compute_similarity(
            "sbert_cosine",
            "sentence_transformers",
            {"text_a": "a", "text_b": "b"},
            {"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        )
        assert captured == ["sentence-transformers/all-MiniLM-L6-v2"]
        assert r["similarity"] == pytest.approx(1.0)

    def test_sbert_cosine_rejects_disallowed_model(self, monkeypatch):
        def fake_get(name):  # must never be reached
            raise AssertionError("should not load a disallowed model")

        monkeypatch.setattr("src.model_cache.get_sbert_model", fake_get)
        clear_all()
        with pytest.raises(ValueError, match="not on the allow-list"):
            compute_similarity(
                "sbert_cosine",
                "sentence_transformers",
                {"text_a": "a", "text_b": "b"},
                {"model_name": "some-arbitrary-hf-model"},
            )

    def test_semantic_search_rejects_disallowed_model(self, monkeypatch):
        def fake_get(name):
            raise AssertionError("should not load a disallowed model")

        monkeypatch.setattr("src.model_cache.get_sbert_model", fake_get)
        clear_all()
        from src.retrieval import compute_retrieval

        with pytest.raises(ValueError, match="not on the allow-list"):
            compute_retrieval(
                "semantic_search",
                "sentence_transformers",
                {"query": "cat", "candidates": ["a cat", "a dog"]},
                {"model_name": "evil-model"},
            )


class TestDiscoveryMetadata:
    # Discovery lists the full catalog, so these run under the pytorch profile
    # (the cpu/default profile omits the PyTorch algorithms they assert on).
    @pytest.mark.parametrize("profile_client", ["pytorch"], indirect=True)
    def test_new_entries_have_semantic_metadata(self, profile_client):
        resp = profile_client().get("/v1/similarity/text/algorithms")
        catalog = resp.json()
        by_key = {(e["algorithm"], e["backend"]): e for e in catalog}

        token_set = by_key[("token_set_overlap", "builtin")]
        assert token_set["category"] == "statistical"
        assert token_set["requires_model"] is False
        assert token_set["requires_gpu"] is False
        assert token_set["variants"] == ["jaccard", "dice"]

        # Legacy aliases are discoverable and point at the canonical family.
        jaccard = by_key[("jaccard", "builtin")]
        assert jaccard["category"] == "statistical"
        assert jaccard["requires_model"] is False
        assert jaccard["alias_of"] == "token_set_overlap"
        assert jaccard["fixed_variant"] == "jaccard"
        dice = by_key[("dice", "builtin")]
        assert dice["alias_of"] == "token_set_overlap"
        assert dice["fixed_variant"] == "dice"

        bm25 = by_key[("bm25", "builtin")]
        assert bm25["category"] == "retrieval"
        assert bm25["requires_model"] is False

        odenet = by_key[("synonym", "odenet")]
        assert odenet["language"] == "de"
        assert odenet["extra"] == "de"

        emb = by_key[("embedding_cosine", "gensim")]
        assert emb["category"] == "word_embedding"
        assert "fasttext" in emb["variants"]
        assert "conceptnet_numberbatch" in emb["variants"]
        # gensim is base-tier now (no [model] extra); large downloads are gated,
        # not gated by a pip extra.
        assert emb["requires_model"] is False
        assert "extra" not in emb

        # semantic_search is now SBERT-only ([model]-only); no base TF-IDF backend.
        sbert = by_key[("semantic_search", "sentence_transformers")]
        assert sbert["requires_model"] is True
        semantic_search_backends = {e["backend"] for e in catalog if e["algorithm"] == "semantic_search"}
        assert semantic_search_backends == {"sentence_transformers"}
        assert ("semantic_search", "gensim") not in by_key


class TestTopicModel:
    """Native corpus-free LSI (replaces the retired DKPro LSA/ESA sidecar)."""

    def test_identical_texts_score_high(self):
        r = compute_similarity(
            "topic_model",
            "builtin",
            {"text_a": "the quick brown fox jumps", "text_b": "the quick brown fox jumps"},
            {"variant": "lsa"},
        )
        assert r["similarity"] == pytest.approx(1.0)

    def test_disjoint_texts_score_low(self):
        r = compute_similarity(
            "topic_model",
            "builtin",
            {"text_a": "the quick brown fox jumps", "text_b": "quantum entanglement particle physics"},
            {"variant": "lsa"},
        )
        assert r["similarity"] < 0.1

    def test_partial_overlap_between_extremes(self):
        r = compute_similarity(
            "topic_model",
            "builtin",
            {"text_a": "the cat sat here", "text_b": "the cat sat there"},
            {"variant": "lsa"},
        )
        assert 0.0 < r["similarity"] <= 1.0

    def test_esa_variant_is_accepted(self):
        r = compute_similarity(
            "topic_model",
            "builtin",
            {"text_a": "the cat sat here", "text_b": "the cat sat there"},
            {"variant": "esa"},
        )
        assert 0.0 <= r["similarity"] <= 1.0

    def test_identical_via_api(self):
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "topic_model",
                "params": {"variant": "lsa"},
                "inputs": [{"id": "p1", "a": "hello world foo bar", "b": "hello world foo bar"}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["backend"] == "builtin"
        assert resp.json()["results"][0]["result"]["similarity"] == pytest.approx(1.0)


class TestStructuralStylistic:
    """Native structural/stylistic measures (replaces the retired DKPro sidecar)."""

    def test_ngram_containment_identical(self):
        r = compute_similarity(
            "structural_stylistic",
            "builtin",
            {"text_a": "the cat sat here", "text_b": "the cat sat here"},
            {"variant": "ngram_containment", "n": 2},
        )
        assert r["similarity"] == pytest.approx(1.0)

    def test_ngram_containment_disjoint(self):
        r = compute_similarity(
            "structural_stylistic",
            "builtin",
            {"text_a": "the cat sat here", "text_b": "banana yellow fruit"},
            {"variant": "ngram_containment", "n": 2},
        )
        assert r["similarity"] == pytest.approx(0.0)

    def test_type_token_ratio_identical(self):
        r = compute_similarity(
            "structural_stylistic",
            "builtin",
            {"text_a": "cat cat cat", "text_b": "cat cat cat"},
            {"variant": "type_token_ratio"},
        )
        assert r["similarity"] == pytest.approx(1.0)

    def test_greedy_string_tiling_identical(self):
        r = compute_similarity(
            "structural_stylistic",
            "builtin",
            {"text_a": "a b c d", "text_b": "a b c d"},
            {"variant": "greedy_string_tiling"},
        )
        assert r["similarity"] == pytest.approx(1.0)

    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError, match="unsupported structural_stylistic variant"):
            compute_similarity("structural_stylistic", "builtin", {"text_a": "a", "text_b": "b"}, {"variant": "nope"})

    def test_via_api(self):
        resp = client.post(
            "/v1/similarity/text/distance",
            json={
                "algorithm": "structural_stylistic",
                "params": {"variant": "ngram_containment", "n": 2},
                "inputs": [{"id": "p1", "a": "the cat sat here", "b": "the cat sat here"}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["backend"] == "builtin"
        assert resp.json()["results"][0]["result"]["similarity"] == pytest.approx(1.0)
