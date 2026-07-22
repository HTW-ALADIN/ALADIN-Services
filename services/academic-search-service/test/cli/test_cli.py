import json

from typer.testing import CliRunner

from cli import app
from cli.commands import search as search_cmd
from config import settings
from core.paper import Paper
from core.search_service import ProviderOutcome, SearchOutcome

runner = CliRunner()


def test_search_cli_prints_json(monkeypatch):
    async def _fake_run_search(**kwargs):
        return SearchOutcome(
            papers=[
                Paper(id="sha256:1", provider="arxiv", backend="scimesh", title="X", year=2024)
            ],
            per_provider={"arxiv": ProviderOutcome(count=1)},
            dedup_report=None,
            took_ms=1.0,
        )

    monkeypatch.setattr(search_cmd, "run_search", _fake_run_search)

    result = runner.invoke(
        app,
        ["search", "--query", '{"text": "x"}', "--providers", "arxiv"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["papers"][0]["title"] == "X"
    assert payload["per_provider"]["arxiv"]["count"] == 1


def test_export_cli_bibtex_from_stdin():
    papers_json = json.dumps(
        {
            "papers": [
                {
                    "id": "sha256:1",
                    "provider": "arxiv",
                    "backend": "scimesh",
                    "title": "Some Paper",
                    "year": 2024,
                }
            ]
        }
    )
    result = runner.invoke(app, ["export", "--format", "bibtex"], input=papers_json)
    assert result.exit_code == 0
    assert "Some Paper" in result.stdout


def test_export_cli_unknown_format_errors():
    papers_json = json.dumps({"papers": []})
    result = runner.invoke(app, ["export", "--format", "unknown"], input=papers_json)
    assert result.exit_code != 0


def test_download_cli_enforces_same_batch_bound_as_api():
    items = [
        {"provider": "arxiv", "paper_id": str(i)}
        for i in range(settings.download_max_batch_size + 1)
    ]
    result = runner.invoke(app, ["download", "--items", json.dumps(items)])
    assert result.exit_code != 0
    assert "DOWNLOAD_MAX_BATCH_SIZE" in result.output
