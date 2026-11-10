import pytest
from pydantic import ValidationError

from core.author import AuthorIdentifier, AuthorQuery


def test_author_identifier_is_empty():
    assert AuthorIdentifier().is_empty()
    assert not AuthorIdentifier(orcid="0000-0002-1825-0097").is_empty()


def test_author_query_requires_name_or_id():
    with pytest.raises(ValidationError):
        AuthorQuery()

    with pytest.raises(ValidationError):
        AuthorQuery(ids=AuthorIdentifier())


def test_author_query_accepts_name_only():
    query = AuthorQuery(name="Jane Smith")
    assert query.has_criteria()


def test_author_query_accepts_id_only():
    query = AuthorQuery(ids=AuthorIdentifier(openalex_author_id="A123"))
    assert query.has_criteria()
