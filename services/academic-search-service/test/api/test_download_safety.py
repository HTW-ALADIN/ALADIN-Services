from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_download_rejects_path_traversal_paper_id():
    response = client.post(
        "/v1/download",
        json={"items": [{"provider": "arxiv", "paper_id": "../../etc/passwd"}]},
    )
    assert response.status_code == 200  # isolated per-item, not a request-level failure
    body = response.json()
    assert body["results"][0]["status"] == "error"
    assert "unsafe_paper_id" in body["results"][0]["error"]
