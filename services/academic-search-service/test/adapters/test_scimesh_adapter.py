from scimesh.models import Author as ScimeshAuthor
from scimesh.models import Paper as ScimeshPaper

from adapters.scimesh_adapter import _normalize


def test_normalize_maps_core_fields():
    raw = ScimeshPaper(
        title="Attention Is All You Need",
        authors=(ScimeshAuthor(name="Ashish Vaswani", affiliation="Google"),),
        year=2017,
        source="semantic_scholar",
        doi="10.1/x",
        citations_count=1000,
        references_count=40,
        pdf_url="https://example.org/paper.pdf",
        url="https://example.org/landing",
        open_access=True,
        extras={"semanticScholarId": "abc123"},
    )

    paper = _normalize(raw, "semantic_scholar")

    assert paper.provider == "semantic_scholar"
    assert paper.backend == "scimesh"
    assert paper.doi == "10.1/x"
    assert paper.external_ids == {"s2": "abc123"}
    assert paper.citation_count == 1000
    assert paper.reference_count == 40
    assert paper.open_access is True
    assert paper.pdf_url == "https://example.org/paper.pdf"
    assert paper.authors[0].name == "Ashish Vaswani"
    assert paper.authors[0].affiliations == ["Google"]


def test_normalize_id_is_doi_based_when_available():
    a = _normalize(
        ScimeshPaper(title="Title A", authors=(), year=2020, source="openalex", doi="10.1/same"),
        "openalex",
    )
    b = _normalize(
        ScimeshPaper(title="Title B", authors=(), year=1999, source="arxiv", doi="10.1/same"),
        "arxiv",
    )
    assert a.id == b.id
