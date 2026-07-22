from core.download_service import download_one


async def test_download_one_unknown_provider():
    result = await download_one("not-a-provider", "x", {})
    assert result.status == "error"
    assert result.error == "unknown_provider"


async def test_download_one_missing_credentials():
    result = await download_one("scopus", "x", {})
    assert result.status == "error"
    assert result.error == "missing_credentials"


async def test_download_one_scimesh_not_found(monkeypatch):
    from adapters import scimesh_adapter

    async def _fake_get(provider, credentials, paper_id):
        return None

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)

    result = await download_one("arxiv", "2401.00001", {})
    assert result.status == "not_found"


async def test_download_one_scimesh_no_pdf_url(monkeypatch):
    from adapters import scimesh_adapter
    from core.paper import Paper

    async def _fake_get(provider, credentials, paper_id):
        return Paper(
            id="sha256:x", provider=provider, backend="scimesh", title="X", open_access=False
        )

    monkeypatch.setattr(scimesh_adapter, "get", _fake_get)

    result = await download_one("arxiv", "2401.00001", {})
    assert result.status == "paywalled"
