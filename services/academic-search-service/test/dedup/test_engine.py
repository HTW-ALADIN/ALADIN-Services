from core.paper import Author, Paper
from dedup.engine import deduplicate


def _paper(**overrides) -> Paper:
    defaults = dict(
        id="sha256:placeholder",
        provider="openalex",
        backend="scimesh",
        title="Attention Is All You Need",
        year=2017,
        authors=[Author(name="Vaswani")],
    )
    defaults.update(overrides)
    return Paper(**defaults)


def test_exact_doi_duplicates_merged():
    a = _paper(id="sha256:same", provider="openalex", doi="10.1/x", abstract="short")
    b = _paper(
        id="sha256:same", provider="crossref", doi="10.1/x", abstract="a much longer abstract here"
    )

    result, report = deduplicate([a, b], strategy="strict")

    assert len(result) == 1
    assert report.input_count == 2
    assert report.output_count == 1
    assert report.duplicates_removed == 1
    assert report.by_tier == {"exact_doi": 1}
    merged = result[0]
    assert merged.abstract == "a much longer abstract here"  # most-complete wins
    assert "crossref" in [m.provider for c in report.clusters for m in c.members]


def test_strict_strategy_does_not_fuzzy_match():
    a = _paper(id="sha256:a", provider="openalex", title="Attention Is All You Need", year=2017)
    b = _paper(id="sha256:b", provider="crossref", title="Attention is all you need", year=2017)

    result, report = deduplicate([a, b], strategy="strict")

    assert len(result) == 2
    assert report.duplicates_removed == 0


def test_auto_strategy_fuzzy_title_year_match():
    a = _paper(id="sha256:a", provider="openalex", title="Attention Is All You Need", year=2017)
    b = _paper(id="sha256:b", provider="crossref", title="Attention is all you need.", year=2017)

    result, report = deduplicate([a, b], strategy="auto")

    assert len(result) == 1
    assert report.by_tier == {"fuzzy_title_year": 1}


def test_no_duplicates_when_titles_differ():
    a = _paper(id="sha256:a", title="Attention Is All You Need", year=2017)
    b = _paper(id="sha256:b", title="Deep Residual Learning for Image Recognition", year=2016)

    result, report = deduplicate([a, b], strategy="auto")

    assert len(result) == 2
    assert report.duplicates_removed == 0
