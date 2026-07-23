import pytest

from core.query import SearchQuery, YearRangeQuery


def test_to_scimesh_query_combines_clauses():
    query = SearchQuery(title="graph neural networks", author="Kipf", year=YearRangeQuery(gte=2020))
    ast = query.to_scimesh_query()
    # Just assert it builds without error and is a Query AST (And-combined).
    assert ast is not None


def test_to_text_query_flattens():
    query = SearchQuery(title="foo", text="bar", author="baz")
    assert query.to_text_query() == "foo bar baz"


def test_empty_query_raises():
    query = SearchQuery()
    with pytest.raises(ValueError):
        query.to_scimesh_query()
    with pytest.raises(ValueError):
        query.to_text_query()
