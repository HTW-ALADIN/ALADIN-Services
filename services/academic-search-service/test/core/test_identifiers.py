import pytest

from core.identifiers import UnsafePaperIdError, assert_safe_paper_id


@pytest.mark.parametrize(
    "paper_id",
    [
        "../../etc/passwd",
        "../secrets",
        "/etc/passwd",
        "\\windows\\system32",
        "10.1101/../../../etc/passwd",
        "",
        "   ",
        "a\x00b",
    ],
)
def test_unsafe_paper_ids_rejected(paper_id):
    with pytest.raises(UnsafePaperIdError):
        assert_safe_paper_id(paper_id)


@pytest.mark.parametrize(
    "paper_id",
    [
        "2401.00001",
        "10.1101/2020.01.01.123456",  # DOI-style, legitimately contains '/'
        "2009/101",  # IACR-style id
        "32790614",
    ],
)
def test_legitimate_paper_ids_accepted(paper_id):
    assert_safe_paper_id(paper_id)  # must not raise
