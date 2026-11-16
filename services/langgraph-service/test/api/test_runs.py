"""End-to-end run tests: graphs -> threads -> runs -> state/history."""

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from starlette.requests import Request

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


def _mock_runs(monkeypatch):
    calls = []

    async def invoke(thread_id, input_data):
        calls.append((thread_id, input_data))
        return input_data

    async def stream(thread_id, input_data):
        calls.append((thread_id, input_data))
        yield {"test_node": input_data}

    monkeypatch.setattr("api.routes.runs.invoke_run", invoke)
    monkeypatch.setattr("api.routes.runs.stream_run", stream)
    return calls


def _assert_run_input_too_large(response, path, limit):
    if path.endswith(":stream"):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "content-length" not in response.headers
        assert response.text == 'data: {"error": "run input too large"}\n\n'
    else:
        assert response.status_code == 413
        assert response.json() == {"detail": f"run input exceeds {limit} bytes"}


def test_graph_request_byte_limit_boundary(monkeypatch):
    graph = {**_GRAPH, "name": "é"}
    body = json.dumps(graph, ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr("config.settings.max_graph_bytes", len(body))

    response = client.post("/v1/graphs", content=body)
    assert response.status_code == 201
    assert response.json()["name"] == "é"

    response = client.post("/v1/graphs", content=body + b" ")
    assert response.status_code == 413
    assert response.json() == {"detail": f"graph definition exceeds {len(body)} bytes"}


@pytest.mark.parametrize(
    ("body", "detail"),
    [(b"{", "invalid JSON:"), (b"\xff", "invalid JSON:"), (b"{}", "invalid graph definition:")],
)
def test_graph_invalid_body_still_returns_400(body, detail):
    response = client.post("/v1/graphs", content=body)
    assert response.status_code == 400
    assert response.json()["detail"].startswith(detail)


@pytest.mark.parametrize("path", ["/v1/threads/th_test/runs", "/v1/threads/th_test/runs:stream"])
def test_run_input_size_and_validation_semantics(monkeypatch, path):
    calls = _mock_runs(monkeypatch)
    input_data = {"query": "é"}
    limit = len(json.dumps(input_data).encode("utf-8"))
    monkeypatch.setattr("config.settings.max_input_bytes", limit)

    response = client.post(path, json={"input": input_data})
    assert response.status_code == 200
    if path.endswith(":stream"):
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: done" in response.text
    else:
        assert response.json() == {"thread_id": "th_test", "output": input_data}
    assert calls == [("th_test", input_data)]

    response = client.post(path, json={})
    assert response.status_code == 200
    assert calls[-1] == ("th_test", {})

    monkeypatch.setattr("config.settings.max_input_bytes", limit - 1)
    response = client.post(path, json={"input": input_data})
    _assert_run_input_too_large(response, path, limit - 1)
    assert len(calls) == 2

    for payload in ({"input": []}, {"input": {}, "unexpected": True}):
        assert client.post(path, json=payload).status_code == 422
    response = client.post(path, content=b'{"input":', headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert len(calls) == 2


@pytest.mark.parametrize("path", ["/v1/threads/th_test/runs", "/v1/threads/th_test/runs:stream"])
@pytest.mark.parametrize("wire_format", ["escaped-unicode", "pretty-printed"])
async def test_run_accepts_expanded_wire_format_at_input_limit(monkeypatch, path, wire_format):
    calls = _mock_runs(monkeypatch)
    if wire_format == "escaped-unicode":
        input_data = {"query": "a" * 4096 + "é𝄞"}
        body = (
            b'{\n    "\\u0069nput": {\n        "query": "'
            + b"\\u0061" * 4096
            + b'\\u00e9\\ud834\\udd1e"\n    }\n}'
        )
    else:
        input_data = {"items": [{"value": i, "label": "é𝄞"} for i in range(200)]}
        body = json.dumps({"input": input_data}, indent=4).encode("utf-8")

    limit = len(json.dumps(input_data).encode("utf-8"))
    assert limit + 1024 < len(body) <= 8 * limit + 1024
    monkeypatch.setattr("config.settings.max_input_bytes", limit)

    async def upload():
        yield body[:13]
        yield body[13:4000]
        yield body[4000:]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        request = async_client.build_request(
            "POST", path, content=upload(), headers={"content-type": "application/json"}
        )
        assert request.headers["transfer-encoding"] == "chunked"
        response = await async_client.send(request)

    assert response.status_code == 200
    assert calls == [("th_test", input_data)]
    if path.endswith(":stream"):
        assert "event: done" in response.text
    else:
        assert response.json()["output"] == input_data


@pytest.mark.parametrize("path", ["/v1/threads/th_test/runs", "/v1/threads/th_test/runs:stream"])
def test_run_request_body_byte_limit_boundary(monkeypatch, path):
    calls = _mock_runs(monkeypatch)
    limit = 64
    monkeypatch.setattr("config.settings.max_input_bytes", limit)
    body = b'{"input": {}}'
    body += b" " * (8 * limit + 1024 - len(body))

    response = client.post(path, content=body, headers={"content-type": "application/json"})
    assert response.status_code == 200
    assert calls == [("th_test", {})]

    response = client.post(path, content=body + b" ", headers={"content-type": "application/json"})
    _assert_run_input_too_large(response, path, limit)
    assert calls == [("th_test", {})]


@pytest.mark.parametrize(
    "path", ["/v1/graphs", "/v1/threads/th_test/runs", "/v1/threads/th_test/runs:stream"]
)
async def test_valid_chunked_request_with_split_utf8_at_limit(monkeypatch, path):
    if path == "/v1/graphs":
        body = json.dumps({**_GRAPH, "name": "é"}, ensure_ascii=False).encode("utf-8")
        monkeypatch.setattr("config.settings.max_graph_bytes", len(body))
    else:
        calls = _mock_runs(monkeypatch)
        input_data = {"query": "é"}
        monkeypatch.setattr(
            "config.settings.max_input_bytes", len(json.dumps(input_data).encode("utf-8"))
        )
        body = json.dumps({"input": input_data}, ensure_ascii=False).encode("utf-8")

    split = body.index("é".encode()) + 1

    async def upload():
        yield body[:1]
        yield body[1:split]
        yield b""
        yield body[split:]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        request = async_client.build_request(
            "POST", path, content=upload(), headers={"content-type": "application/json"}
        )
        assert request.headers["transfer-encoding"] == "chunked"
        response = await async_client.send(request)

    if path == "/v1/graphs":
        assert response.status_code == 201
        assert response.json()["name"] == "é"
    else:
        assert response.status_code == 200
        assert calls == [("th_test", input_data)]
        if path.endswith(":stream"):
            assert "event: done" in response.text
        else:
            assert response.json()["output"] == input_data


@pytest.mark.parametrize(
    ("path", "setting"),
    [
        ("/v1/graphs", "max_graph_bytes"),
        ("/v1/threads/th_test/runs", "max_input_bytes"),
        ("/v1/threads/th_test/runs:stream", "max_input_bytes"),
    ],
)
@pytest.mark.parametrize("declared_length", [None, "1"], ids=["chunked", "incorrect-length"])
@pytest.mark.parametrize(
    "first_chunk_oversized", [False, True], ids=["incremental", "single-chunk"]
)
async def test_oversized_request_stops_before_buffering_or_parsing(
    monkeypatch, path, setting, declared_length, first_chunk_oversized
):
    limit = 32
    monkeypatch.setattr(f"config.settings.{setting}", limit)
    body_limit = limit if setting == "max_graph_bytes" else 8 * limit + 1024

    def fail_graph_json(*args, **kwargs):
        pytest.fail("oversized graph body was parsed")

    async def fail_run_json(self):
        pytest.fail("oversized run body was parsed")

    if setting == "max_graph_bytes":
        monkeypatch.setattr("api.routes.graphs.json", SimpleNamespace(loads=fail_graph_json))
    else:
        monkeypatch.setattr(Request, "json", fail_run_json)

    if first_chunk_oversized:
        chunks = [b"x" * (body_limit + 1), b"unread"]
    else:
        chunks = [b"x" * body_limit, b"x", b"unread"]
    consumed = []

    async def upload():
        for chunk in chunks:
            consumed.append(chunk)
            yield chunk

    headers = {"content-type": "application/json"}
    if declared_length is not None:
        headers["content-length"] = declared_length
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        request = async_client.build_request("POST", path, content=upload(), headers=headers)
        if declared_length is None:
            assert request.headers["transfer-encoding"] == "chunked"
            assert "content-length" not in request.headers
        response = await async_client.send(request)

    assert consumed == chunks[:-1]
    if setting == "max_graph_bytes":
        assert response.status_code == 413
        assert response.json() == {"detail": f"graph definition exceeds {limit} bytes"}
    else:
        _assert_run_input_too_large(response, path, limit)
