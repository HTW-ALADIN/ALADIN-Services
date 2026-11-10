import httpx
import pytest
import respx

from adapters import author_adapter
from core.author import AuthorIdentifier, AuthorQuery


@respx.mock
async def test_openalex_search_authors_by_name():
    respx.get("https://api.openalex.org/authors").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/A5023888391",
                        "display_name": "Jane Smith",
                        "orcid": "https://orcid.org/0000-0002-1825-0097",
                        "works_count": 42,
                        "cited_by_count": 1000,
                        "summary_stats": {"h_index": 12},
                        "last_known_institutions": [{"display_name": "Example University"}],
                    }
                ]
            },
        )
    )

    authors = await author_adapter.search_authors(
        "openalex", AuthorQuery(name="Jane Smith"), {}, 10
    )

    assert len(authors) == 1
    author = authors[0]
    assert author.provider == "openalex"
    assert author.name == "Jane Smith"
    assert author.external_ids == {"openalex": "A5023888391", "orcid": "0000-0002-1825-0097"}
    assert author.orcid == "0000-0002-1825-0097"
    assert author.paper_count == 42
    assert author.citation_count == 1000
    assert author.h_index == 12
    assert author.affiliations == ["Example University"]


@respx.mock
async def test_openalex_search_authors_by_id_direct_lookup():
    route = respx.get("https://api.openalex.org/authors/A5023888391").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "https://openalex.org/A5023888391",
                "display_name": "Jane Smith",
                "works_count": 42,
                "cited_by_count": 1000,
            },
        )
    )

    query = AuthorQuery(ids=AuthorIdentifier(openalex_author_id="A5023888391"))
    authors = await author_adapter.search_authors("openalex", query, {}, 10)

    assert route.called
    assert authors[0].external_ids["openalex"] == "A5023888391"


@respx.mock
async def test_openalex_search_authors_by_id_not_found():
    respx.get("https://api.openalex.org/authors/A_missing").mock(return_value=httpx.Response(404))

    query = AuthorQuery(ids=AuthorIdentifier(openalex_author_id="A_missing"))
    authors = await author_adapter.search_authors("openalex", query, {}, 10)

    assert authors == []


@respx.mock
async def test_openalex_papers_by_author_id_normalizes_to_paper():
    respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Some Paper",
                        "authorships": [
                            {"author": {"display_name": "Jane Smith"}, "institutions": []}
                        ],
                        "publication_year": 2021,
                        "doi": "https://doi.org/10.1/x",
                        "id": "https://openalex.org/W123",
                    }
                ],
                "meta": {"next_cursor": None},
            },
        )
    )

    query = AuthorQuery(ids=AuthorIdentifier(openalex_author_id="A5023888391"))
    papers = await author_adapter.papers_by_author("openalex", query, {}, 10)

    assert len(papers) == 1
    assert papers[0].title == "Some Paper"
    assert papers[0].provider == "openalex"
    assert papers[0].doi == "10.1/x"


@respx.mock
async def test_semantic_scholar_search_authors_by_name():
    respx.get("https://api.semanticscholar.org/graph/v1/author/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "authorId": "12345",
                        "name": "Jane Smith",
                        "paperCount": 10,
                        "citationCount": 500,
                        "hIndex": 5,
                        "externalIds": {"ORCID": "0000-0002-1825-0097"},
                    }
                ]
            },
        )
    )

    authors = await author_adapter.search_authors(
        "semantic_scholar", AuthorQuery(name="Jane Smith"), {}, 10
    )

    assert len(authors) == 1
    assert authors[0].external_ids == {"semantic_scholar": "12345", "orcid": "0000-0002-1825-0097"}
    assert authors[0].h_index == 5


@respx.mock
async def test_semantic_scholar_papers_by_author_id():
    respx.get("https://api.semanticscholar.org/graph/v1/author/12345/papers").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"paperId": "abc123", "title": "Some Paper", "year": 2020}]},
        )
    )

    query = AuthorQuery(ids=AuthorIdentifier(semantic_scholar_author_id="12345"))
    papers = await author_adapter.papers_by_author("semantic_scholar", query, {}, 10)

    assert len(papers) == 1
    assert papers[0].title == "Some Paper"
    assert papers[0].provider == "semantic_scholar"


async def test_scopus_requires_api_key_for_search():
    with pytest.raises(ValueError):
        await author_adapter.search_authors("scopus", AuthorQuery(name="Jane Smith"), {}, 10)


@respx.mock
async def test_scopus_author_id_lookup_parses_retrieval_response_shape():
    # The Author Retrieval API's response shape differs from the Author
    # Search API: identity/affiliation data is nested under `coredata` and
    # `author-profile`, not at the top level of the entry.
    respx.get("https://api.elsevier.com/content/author/author_id/7004212771").mock(
        return_value=httpx.Response(
            200,
            json={
                "author-retrieval-response": [
                    {
                        "coredata": {
                            "dc:identifier": "AUTHOR_ID:7004212771",
                            "document-count": "42",
                        },
                        "author-profile": {
                            "preferred-name": {"given-name": "Jane", "surname": "Smith"},
                            "affiliation-current": {
                                "affiliation": {"ip-doc": {"afdispname": "Example University"}}
                            },
                        },
                    }
                ]
            },
        )
    )

    query = AuthorQuery(ids=AuthorIdentifier(scopus_author_id="7004212771"))
    authors = await author_adapter.search_authors("scopus", query, {"api_key": "test-key"}, 10)

    assert len(authors) == 1
    author = authors[0]
    assert author.name == "Jane Smith"
    assert author.external_ids == {"scopus": "7004212771"}
    assert author.paper_count == 42
    assert author.affiliations == ["Example University"]


@respx.mock
async def test_scopus_search_authors_by_name_escapes_query_dsl():
    route = respx.get("https://api.elsevier.com/content/search/author").mock(
        return_value=httpx.Response(200, json={"search-results": {"entry": []}})
    )

    query = AuthorQuery(name='Smith) OR AUTHLASTNAME("Jones')
    await author_adapter.search_authors("scopus", query, {"api_key": "test-key"}, 10)

    sent_query = route.calls.last.request.url.params["query"]
    # The only structural characters allowed are the single wrapping
    # AUTHLASTNAME(...) added by the adapter itself; the user-supplied value
    # must have had all of its own "(", ")", '"', and boolean operators
    # stripped so it can't close the function early or inject a new clause.
    assert sent_query.startswith("AUTHLASTNAME(")
    assert sent_query.endswith(")")
    inner = sent_query[len("AUTHLASTNAME(") : -1]
    assert "(" not in inner
    assert ")" not in inner
    assert '"' not in inner
    assert "OR" not in inner


async def test_scopus_papers_by_author_rejects_malformed_author_id():
    query = AuthorQuery(ids=AuthorIdentifier(scopus_author_id="123/../secret"))
    with pytest.raises(ValueError):
        await author_adapter.papers_by_author("scopus", query, {"api_key": "test-key"}, 10)


async def test_openalex_search_authors_rejects_malformed_id_path_segment():
    query = AuthorQuery(ids=AuthorIdentifier(openalex_author_id="../W123"))
    with pytest.raises(ValueError):
        await author_adapter.search_authors("openalex", query, {}, 10)
