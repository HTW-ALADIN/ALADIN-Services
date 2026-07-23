import json

import pytest

from core.paper import Author, Paper
from export import export


@pytest.fixture
def paper() -> Paper:
    return Paper(
        id="sha256:abc",
        provider="openalex",
        backend="scimesh",
        title="Attention Is All You Need",
        year=2017,
        venue="NeurIPS",
        doi="10.1/x",
        authors=[Author(name="Ashish Vaswani"), Author(name="Noam Shazeer")],
        abstract="We propose a new architecture.",
        landing_page_url="https://example.org/paper",
    )


def test_bibtex_contains_key_fields(paper):
    body = export([paper], "bibtex").decode("utf-8")
    assert "@article{Vaswani2017" in body
    assert "title = {Attention Is All You Need}" in body
    assert "doi = {10.1/x}" in body


def test_ris_contains_key_fields(paper):
    body = export([paper], "ris").decode("utf-8")
    assert "TI  - Attention Is All You Need" in body
    assert "AU  - Ashish Vaswani" in body
    assert "DO  - 10.1/x" in body
    assert body.strip().endswith("ER  -")


def test_csv_has_header_and_row(paper):
    body = export([paper], "csv").decode("utf-8")
    lines = body.strip().splitlines()
    assert lines[0].startswith("id,title,authors")
    assert "Attention Is All You Need" in lines[1]


def test_json_roundtrips(paper):
    body = export([paper], "json").decode("utf-8")
    data = json.loads(body)
    assert data[0]["title"] == "Attention Is All You Need"
    assert data[0]["doi"] == "10.1/x"


def test_unknown_format_raises(paper):
    with pytest.raises(KeyError):
        export([paper], "endnote")
