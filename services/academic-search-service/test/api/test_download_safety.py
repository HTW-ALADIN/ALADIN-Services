from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adapters import academic_mcp_adapter
from config import settings
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


@pytest.mark.parametrize("allowed", [False, True])
def test_fulltext_respects_academic_mcp_download_gate(monkeypatch, allowed):
    reader = AsyncMock(return_value="extracted text")
    monkeypatch.setattr(settings, "academic_mcp_downloads_allowed", allowed)
    monkeypatch.setattr(academic_mcp_adapter, "read_fulltext", reader)

    response = client.get("/v1/fulltext", params={"provider": "pubmed", "paper_id": "32790614"})

    if allowed:
        assert response.status_code == 200
        assert response.json()["text"] == "extracted text"
        reader.assert_awaited_once()
    else:
        assert response.status_code == 400
        assert "ACADEMIC_MCP_DOWNLOADS_ALLOWED" in response.json()["detail"]
        reader.assert_not_awaited()
