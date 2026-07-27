import pytest

from core.url_safety import UnsafeUrlError, assert_safe_url, is_safe_url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/",
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "ftp://example.org/file.pdf",
    ],
)
def test_unsafe_urls_rejected(url):
    assert not is_safe_url(url)
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://arxiv.org/pdf/2401.00001.pdf",
        "http://example.com/paper.pdf",
    ],
)
def test_safe_urls_accepted(url):
    assert is_safe_url(url)
    assert_safe_url(url)
