"""CLI parity tests: JSON in, JSON out over the same core functions."""

import json

import respx
from typer.testing import CliRunner

from cli import app

runner = CliRunner()

_GRAPH = {
    "name": "echo",
    "nodes": [
        {"id": "a", "type": "transform", "operations": [{"op": "const", "value": 1}]},
    ],
    "edges": [],
    "entry": "a",
}

_LLM_GRAPH = {
    "name": "llm-echo",
    "nodes": [
        {
            "id": "gen",
            "type": "llm",
            "provider": "openai",
            "model": "gpt-4o",
            "input_key": "query",
            "output_key": "summary",
        }
    ],
    "edges": [],
    "entry": "gen",
}

_GATEWAY_RESPONSE = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-4o",
    "provider": "openai",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
    ],
    "usage": {},
}


def test_cli_graph_thread_run_roundtrip(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_GRAPH))

    created = runner.invoke(app, ["graph", "create", "--file", str(path)])
    assert created.exit_code == 0, created.output
    graph_id = json.loads(created.output)["graph_id"]

    listed = runner.invoke(app, ["graph", "list"])
    assert listed.exit_code == 0, listed.output
    assert graph_id in listed.output

    fetched = runner.invoke(app, ["graph", "get", graph_id])
    assert fetched.exit_code == 0, fetched.output
    assert json.loads(fetched.output)["definition"]["name"] == "echo"

    thread = runner.invoke(app, ["thread", "create", "--graph", graph_id])
    assert thread.exit_code == 0, thread.output
    thread_id = json.loads(thread.output)["thread_id"]

    invoked = runner.invoke(app, ["run", "invoke", thread_id, "--input", '{"start": true}'])
    assert invoked.exit_code == 0, invoked.output
    assert json.loads(invoked.output)["output"]["value"] == 1

    state = runner.invoke(app, ["thread", "state", thread_id])
    assert state.exit_code == 0, state.output
    assert json.loads(state.output)["values"]["value"] == 1

    history = runner.invoke(app, ["thread", "history", thread_id])
    assert history.exit_code == 0, history.output
    assert len(json.loads(history.output)["history"]) >= 1

    assert runner.invoke(app, ["thread", "delete", thread_id]).exit_code == 0
    assert runner.invoke(app, ["graph", "delete", graph_id]).exit_code == 0


def test_cli_run_invoke_with_mocked_gateway(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.llm_gateway_api_key", "secret")
    path = tmp_path / "llm.json"
    path.write_text(json.dumps(_LLM_GRAPH))
    graph_id = json.loads(runner.invoke(app, ["graph", "create", "--file", str(path)]).output)[
        "graph_id"
    ]
    thread_id = json.loads(runner.invoke(app, ["thread", "create", "--graph", graph_id]).output)[
        "thread_id"
    ]
    with respx.mock(base_url="http://localhost:8002", assert_all_called=True) as mock:
        mock.post("/generate").respond(200, json=_GATEWAY_RESPONSE)
        invoked = runner.invoke(app, ["run", "invoke", thread_id, "--input", '{"query": "hi"}'])
    assert invoked.exit_code == 0, invoked.output
    assert json.loads(invoked.output)["output"]["summary"] == "hello"
