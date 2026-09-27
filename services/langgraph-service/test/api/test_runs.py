"""End-to-end run tests: graphs -> threads -> runs -> state/history."""

import respx
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_GRAPH = {
    "name": "echo",
    "nodes": [
        {
            "id": "gen",
            "type": "llm",
            "provider": "openai",
            "model": "gpt-4o",
            "input_key": "query",
            "output_key": "summary",
        },
        {
            "id": "pick",
            "type": "transform",
            "operations": [{"op": "pick", "from_key": "summary"}],
        },
    ],
    "edges": [["gen", "pick"]],
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


def _setup_graph_and_thread(monkeypatch):
    monkeypatch.setattr("config.settings.llm_gateway_api_key", "secret")
    with respx.mock(base_url="http://localhost:8002", assert_all_called=False) as mock:
        mock.post("/generate").respond(200, json=_GATEWAY_RESPONSE)
        graph_id = client.post("/v1/graphs", json=_GRAPH).json()["graph_id"]
        thread_id = client.post("/v1/threads", json={"graph_id": graph_id}).json()["thread_id"]
        run = client.post(f"/v1/threads/{thread_id}/runs", json={"input": {"query": "hi"}}).json()
        return graph_id, thread_id, run, mock


def test_full_run_lifecycle(monkeypatch):
    graph_id, thread_id, run, _ = _setup_graph_and_thread(monkeypatch)
    assert run["output"]["summary"] == "hello"

    state = client.get(f"/v1/threads/{thread_id}/state").json()
    assert state["values"]["summary"] == "hello"
    assert state["graph_id"] == graph_id

    history = client.get(f"/v1/threads/{thread_id}/history").json()
    assert len(history["history"]) >= 1

    # A second run on the same thread sees accumulated state.
    with respx.mock(base_url="http://localhost:8002") as mock:
        mock.post("/generate").respond(200, json=_GATEWAY_RESPONSE)
        second = client.post(
            f"/v1/threads/{thread_id}/runs", json={"input": {"query": "again"}}
        ).json()
    assert second["output"]["summary"] == "hello"


def test_unknown_graph_and_thread():
    assert client.post("/v1/threads", json={"graph_id": "gr_missing"}).status_code == 404
    response = client.post("/v1/threads/th_missing/runs", json={"input": {}})
    assert response.status_code == 404


def test_unsafe_http_graph_rejected():
    bad = {
        "name": "bad",
        "nodes": [
            {
                "id": "call",
                "type": "http",
                "url": "http://127.0.0.1:8003/v1/search",
                "output_key": "out",
            }
        ],
        "edges": [],
        "entry": "call",
    }
    response = client.post("/v1/graphs", json=bad)
    assert response.status_code == 400


def test_gateway_failure_maps_to_502(monkeypatch):
    monkeypatch.setattr("config.settings.llm_gateway_api_key", "secret")
    with respx.mock(base_url="http://localhost:8002") as mock:
        mock.post("/generate").respond(500, text="boom")
        graph_id = client.post("/v1/graphs", json=_GRAPH).json()["graph_id"]
        thread_id = client.post("/v1/threads", json={"graph_id": graph_id}).json()["thread_id"]
        response = client.post(f"/v1/threads/{thread_id}/runs", json={"input": {"query": "hi"}})
    assert response.status_code == 502
    assert response.json()["detail"]["node_id"] == "gen"


def test_run_crud_roundtrip():
    created = client.post("/v1/graphs", json=_GRAPH).json()
    assert client.get("/v1/graphs").json()["graphs"]
    fetched = client.get(f"/v1/graphs/{created['graph_id']}").json()
    assert fetched["definition"]["name"] == "echo"

    thread = client.post("/v1/threads", json={"graph_id": created["graph_id"]}).json()
    assert client.delete(f"/v1/threads/{thread['thread_id']}").status_code == 204
    assert client.delete(f"/v1/graphs/{created['graph_id']}").status_code == 204
    assert client.get(f"/v1/graphs/{created['graph_id']}").status_code == 404


def test_streaming_emits_node_frames(monkeypatch):
    monkeypatch.setattr("config.settings.llm_gateway_api_key", "secret")
    graph_id = client.post("/v1/graphs", json=_GRAPH).json()["graph_id"]
    thread_id = client.post("/v1/threads", json={"graph_id": graph_id}).json()["thread_id"]
    with respx.mock(base_url="http://localhost:8002", assert_all_called=False) as mock:
        mock.post("/generate").respond(200, json=_GATEWAY_RESPONSE)
        response = client.post(
            f"/v1/threads/{thread_id}/runs:stream", json={"input": {"query": "hi"}}
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "data:" in response.text
    assert "gen" in response.text
