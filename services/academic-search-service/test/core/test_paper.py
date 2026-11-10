from core.paper import compute_paper_id, normalize_title


def test_normalize_title_strips_punctuation_and_case():
    assert normalize_title("Graph Neural Networks: A Review!") == "graph neural networks a review"


def test_compute_paper_id_prefers_doi():
    a = compute_paper_id(doi="10.1/x", arxiv_id="2401.0001", title="Foo", year=2024)
    b = compute_paper_id(doi="10.1/x", title="Different Title", year=1999)
    assert a == b


def test_compute_paper_id_falls_back_to_title_year():
    a = compute_paper_id(title="Some Paper", year=2024)
    b = compute_paper_id(title="some paper", year=2024)
    c = compute_paper_id(title="Some Paper", year=2023)
    assert a == b
    assert a != c


def test_compute_paper_id_doi_case_insensitive():
    a = compute_paper_id(doi="10.1/ABC", title="x", year=1)
    b = compute_paper_id(doi="10.1/abc", title="x", year=1)
    assert a == b
