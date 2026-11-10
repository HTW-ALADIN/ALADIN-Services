from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_PAPER = {
    "id": "sha256:abc",
    "provider": "openalex",
    "backend": "scimesh",
    "title": "Attention Is All You Need",
    "year": 2017,
    "doi": "10.1/x",
    "authors": [{"name": "Ashish Vaswani"}],
}


def test_export_bibtex():
    response = client.post("/v1/export", json={"papers": [_PAPER], "format": "bibtex"})
    assert response.status_code == 200
    assert "application/x-bibtex" in response.headers["content-type"]
    assert "Attention Is All You Need" in response.text


def test_export_json():
    response = client.post("/v1/export", json={"papers": [_PAPER], "format": "json"})
    assert response.status_code == 200
    assert response.json()[0]["doi"] == "10.1/x"


def test_export_unknown_format_returns_error():
    response = client.post("/v1/export", json={"papers": [_PAPER], "format": "endnote"})
    assert (
        response.status_code == 422
    )  # rejected by the ExportFormat Literal before it hits export()
