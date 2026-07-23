from datetime import datetime

from academic_mcp.types import Paper as AcademicMcpPaper

from adapters.academic_mcp_adapter import _normalize


def test_normalize_maps_core_fields():
    raw = AcademicMcpPaper(
        paper_id="32790614",
        title="A Study",
        authors=["Jane Doe", "John Roe"],
        abstract="An abstract.",
        doi="10.1/y",
        published_date=datetime(2021, 5, 1),
        pdf_url="https://example.org/a.pdf",
        url="https://example.org/a",
        source="pubmed",
        citations=12,
    )

    paper = _normalize(raw, "pubmed")

    assert paper.provider == "pubmed"
    assert paper.backend == "academic_mcp"
    # `doi` external_id is only populated for the crossref provider (see
    # _normalize) -- pubmed papers get their DOI from the top-level `doi`
    # field instead.
    assert paper.external_ids == {"pmid": "32790614"}
    assert paper.doi == "10.1/y"
    assert paper.year == 2021
    assert paper.citation_count == 12
    assert [a.name for a in paper.authors] == ["Jane Doe", "John Roe"]
    assert paper.pdf_url == "https://example.org/a.pdf"


def test_normalize_id_matches_scimesh_for_same_doi():
    from academic_mcp.types import Paper as AcademicMcpPaper
    from scimesh.models import Paper as ScimeshPaper

    from adapters.scimesh_adapter import _normalize as scimesh_normalize

    mcp_paper = _normalize(
        AcademicMcpPaper(
            paper_id="x",
            title="Different Title",
            authors=[],
            abstract="",
            doi="10.1/shared",
            published_date=None,
            pdf_url="",
            url="",
            source="crossref",
        ),
        "crossref",
    )
    scimesh_paper = scimesh_normalize(
        ScimeshPaper(
            title="Other Title", authors=(), year=2000, source="openalex", doi="10.1/shared"
        ),
        "openalex",
    )
    assert mcp_paper.id == scimesh_paper.id
