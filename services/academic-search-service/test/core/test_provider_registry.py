import pytest

from core.provider_registry import (
    get_provider_spec,
    providers_supporting_author_search,
    providers_supporting_citations,
)


def test_get_provider_spec_known():
    spec = get_provider_spec("openalex")
    assert spec.backend == "scimesh"
    assert spec.supports_citations


def test_get_provider_spec_unknown_raises():
    with pytest.raises(KeyError):
        get_provider_spec("not-a-provider")


def test_scopus_requires_api_key():
    spec = get_provider_spec("scopus")
    assert spec.required_credential_names == ("api_key",)


def test_providers_supporting_citations_matches_scimesh_only():
    citing_providers = set(providers_supporting_citations())
    assert citing_providers == {"openalex", "semantic_scholar", "scopus"}


def test_providers_supporting_author_search_matches_scimesh_only():
    author_providers = set(providers_supporting_author_search())
    assert author_providers == {"openalex", "semantic_scholar", "scopus"}


def test_author_id_fields_declared_per_provider():
    assert get_provider_spec("openalex").author_id_fields == ("openalex_author_id", "orcid")
    assert get_provider_spec("semantic_scholar").author_id_fields == ("semantic_scholar_author_id",)
    assert get_provider_spec("scopus").author_id_fields == ("scopus_author_id",)
