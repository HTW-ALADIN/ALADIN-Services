from core.credentials import redact, resolve_credentials


def test_resolve_credentials_ok_when_no_required_fields():
    resolution = resolve_credentials("arxiv", None)
    assert resolution.ok
    assert resolution.credentials == {}
    assert resolution.errors == []


def test_resolve_credentials_missing_required_field():
    resolution = resolve_credentials("scopus", None)
    assert not resolution.ok
    assert resolution.errors == ["missing_credentials"]


def test_resolve_credentials_present_required_field():
    resolution = resolve_credentials("scopus", {"api_key": "secret"})
    assert resolution.ok
    assert resolution.credentials == {"api_key": "secret"}


def test_resolve_credentials_filters_unknown_fields():
    resolution = resolve_credentials("openalex", {"mailto": "a@b.com", "unexpected": "x"})
    assert resolution.ok
    assert resolution.credentials == {"mailto": "a@b.com"}


def test_resolve_credentials_unknown_provider_raises():
    import pytest

    with pytest.raises(KeyError):
        resolve_credentials("not-a-real-provider", None)


def test_redact_masks_credential_shaped_fields():
    payload = {
        "credentials": {"scopus": {"api_key": "shh"}},
        "query": {"text": "hello"},
        "nested": {"mailto": "a@b.com"},
    }
    redacted = redact(payload)
    assert redacted["credentials"]["scopus"]["api_key"] == "***"
    assert redacted["nested"]["mailto"] == "***"
    assert redacted["query"]["text"] == "hello"
