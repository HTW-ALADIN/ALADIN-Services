from __future__ import annotations

from openai_wrapper_service.config import openai_client_options


def test_openai_client_options_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-test")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "project-test")
    monkeypatch.setenv("OPENAI_WRAPPER_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OPENAI_WRAPPER_MAX_RETRIES", "4")

    assert openai_client_options() == {
        "api_key": "test-key",
        "base_url": "https://provider.example/v1",
        "organization": "org-test",
        "project": "project-test",
        "timeout": 12.5,
        "max_retries": 4,
    }
