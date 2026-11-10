import asyncio

from config import settings
from core.provider_fanout import run_provider


async def test_run_provider_unknown_provider():
    result, errors = await run_provider("not-a-provider", {}, lambda spec, creds: _noop(), [])
    assert result == []
    assert errors == ["unknown_provider"]


async def test_run_provider_missing_credentials():
    result, errors = await run_provider("scopus", {}, lambda spec, creds: _noop(), [])
    assert result == []
    assert errors == ["missing_credentials"]


async def test_run_provider_success_passes_resolved_credentials():
    seen = {}

    async def build_coro(spec, creds):
        seen["backend"] = spec.backend
        seen["credentials"] = creds
        return ["ok"]

    result, errors = await run_provider(
        "openalex", {"openalex": {"mailto": "team@example.org"}}, build_coro, []
    )
    assert result == ["ok"]
    assert errors == []
    assert seen["backend"] == "scimesh"
    assert seen["credentials"] == {"mailto": "team@example.org"}


async def test_run_provider_exception_isolated():
    async def build_coro(spec, creds):
        raise RuntimeError("boom")

    result, errors = await run_provider("openalex", {}, build_coro, [])
    assert result == []
    assert errors == ["provider_error: boom"]


async def test_run_provider_timeout_isolated(monkeypatch):
    monkeypatch.setattr(settings, "provider_timeout_seconds", 0.05)

    async def build_coro(spec, creds):
        await asyncio.sleep(10)
        return []

    result, errors = await run_provider("openalex", {}, build_coro, [])
    assert result == []
    assert errors[0].startswith("provider_timeout")


async def _noop():
    return []
