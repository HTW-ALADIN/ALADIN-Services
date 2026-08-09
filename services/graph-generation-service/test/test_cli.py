import json

import pytest

from app.cli import run


def test_generate_outputs_requested_graph_format(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "algorithm": "barabasi_albert",
        "backend": "networkx",
        "params": {"n": 10, "m": 2, "seed": 42},
        "output": {"format": "edge_list"},
    }

    assert run(["generate", json.dumps(payload)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["format"] == "edge_list"
    assert len(output["nodes"]) == 10


def test_generate_reports_validation_errors(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {"algorithm": "barabasi_albert", "backend": "networkx", "params": {"n": 10}}

    assert run(["generate", json.dumps(payload)]) == 2
    assert "error" in json.loads(capsys.readouterr().err)
