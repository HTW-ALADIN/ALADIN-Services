"""Unit tests for SSRF-safety checks."""

import pytest

from core.url_safety import UnsafeUrlError, assert_safe_url, is_safe_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/api",
        "http://example.com:8080/v1/search",
    ],
)
def test_safe_urls_pass(url):
    assert is_safe_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8003/v1/search",
        "http://127.0.0.1:8000/x",
        "http://10.1.2.3/api",
        "http://192.168.1.10/api",
        "http://172.16.0.5/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/x",
        "ftp://example.com/file",
        "http:///no-host",
    ],
)
def test_unsafe_urls_rejected(url):
    assert is_safe_url(url) is False
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)
