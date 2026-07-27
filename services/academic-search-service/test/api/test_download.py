from fastapi.testclient import TestClient

from api.routes import download as download_route
from core.download_service import DownloadResult
from main import app

client = TestClient(app)


def test_download_bounded_batch_rejected():
    items = [{"provider": "arxiv", "paper_id": str(i)} for i in range(25)]
    response = client.post("/v1/download", json={"items": items})
    assert response.status_code == 422


def test_download_empty_batch_rejected():
    response = client.post("/v1/download", json={"items": []})
    assert response.status_code == 422


def test_download_success(monkeypatch):
    async def _fake_download_one(provider, paper_id, credentials):
        return DownloadResult(provider=provider, paper_id=paper_id, status="ok", path="/tmp/x.pdf")

    monkeypatch.setattr(download_route, "download_one", _fake_download_one)

    response = client.post(
        "/v1/download", json={"items": [{"provider": "arxiv", "paper_id": "2401.00001"}]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["status"] == "ok"
    assert body["results"][0]["path"] == "/tmp/x.pdf"
