"""Unit tests for node executors (gateway/HTTP mocked, no live network)."""

import gzip

import httpx
import pytest
import respx

from core.dsl import HTTPNode, LLMNode, TransformNode
from core.errors import NodeExecutionError
from core.nodes.http_tool import execute_http_node
from core.nodes.llm import build_request, execute_llm_node
from core.nodes.transform import execute_transform_node


def _llm_node(**overrides):
    payload = {
        "id": "gen",
        "type": "llm",
        "provider": "openai",
        "model": "gpt-4o",
        "input_key": "query",
        "output_key": "summary",
    }
    payload.update(overrides)
    return LLMNode.model_validate(payload)


def test_llm_build_request_openai_chat_shape():
    node = _llm_node(system="Be brief.")
    body = build_request(node, {"query": "hello"})
    assert body["format"] == "openai-chat"
    assert body["provider"] == "openai"
    assert body["messages"][0] == {"role": "system", "content": "Be brief."}
    assert body["messages"][1] == {"role": "user", "content": "hello"}


async def test_llm_node_success():
    node = _llm_node()
    gateway_response = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-4o",
        "provider": "openai",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {},
    }
    with respx.mock(base_url="http://gateway:8002", assert_all_called=True) as mock:
        mock.post("/generate").respond(200, json=gateway_response)
        async with httpx.AsyncClient(base_url="http://gateway:8002") as client:
            update = await execute_llm_node(
                node,
                {"query": "hello"},
                gateway_base_url="http://gateway:8002",
                gateway_api_key="secret",
                timeout_seconds=5.0,
                retry_once=False,
                client=client,
            )
    assert update == {"summary": "hi"}


async def test_llm_node_missing_key_fails_fast():
    node = _llm_node()
    with pytest.raises(NodeExecutionError, match="LLM_GATEWAY_API_KEY"):
        await execute_llm_node(
            node,
            {"query": "hello"},
            gateway_base_url="http://gateway:8002",
            gateway_api_key="",
            timeout_seconds=5.0,
            retry_once=False,
        )


async def test_llm_node_gateway_error_maps_to_502():
    node = _llm_node()
    with respx.mock(base_url="http://gateway:8002", assert_all_called=True) as mock:
        mock.post("/generate").respond(500, text="boom")
        async with httpx.AsyncClient(base_url="http://gateway:8002") as client:
            with pytest.raises(NodeExecutionError) as exc_info:
                await execute_llm_node(
                    node,
                    {"query": "hello"},
                    gateway_base_url="http://gateway:8002",
                    gateway_api_key="secret",
                    timeout_seconds=5.0,
                    retry_once=False,
                    client=client,
                )
    assert exc_info.value.upstream_status == 500


async def test_http_node_success_and_template(monkeypatch):
    async def resolve(host, port, *, allow_internal=False):
        return "8.8.8.8"

    monkeypatch.setattr("core.nodes.http_tool.resolve_safe_address", resolve)
    node = HTTPNode.model_validate(
        {
            "id": "search",
            "type": "http",
            "url": "https://api.example.com/v1/search",
            "method": "POST",
            "body_template": {"query": "$.query"},
            "output_key": "papers",
        }
    )
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://8.8.8.8/v1/search").respond(200, json={"hits": [1]})
        async with httpx.AsyncClient() as client:
            update = await execute_http_node(
                node, {"query": "gnn"}, timeout_seconds=5.0, max_response_bytes=1024, client=client
            )
        assert route.call_count == 1
        assert route.calls[0].request.content == b'{"query":"gnn"}'
        assert route.calls[0].request.headers["host"] == "api.example.com"
        assert route.calls[0].request.extensions["sni_hostname"] == "api.example.com"
    assert update == {"papers": {"hits": [1]}}


async def test_http_node_rejects_unsafe_url():
    node = HTTPNode.model_validate(
        {
            "id": "search",
            "type": "http",
            "url": "https://api.example.com/v1/search",
            "output_key": "papers",
        }
    )
    node.url = "http://127.0.0.1:8003/v1/search"
    with pytest.raises(NodeExecutionError, match="unsafe"):
        await execute_http_node(node, {}, timeout_seconds=5.0, max_response_bytes=1024)


async def test_http_node_response_cap(monkeypatch):
    async def resolve(host, port, *, allow_internal=False):
        return "8.8.8.8"

    monkeypatch.setattr("core.nodes.http_tool.resolve_safe_address", resolve)
    node = HTTPNode.model_validate(
        {"id": "call", "type": "http", "url": "https://api.example.com/big", "output_key": "out"}
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://8.8.8.8/big").respond(200, content=b"x" * 64)
        async with httpx.AsyncClient() as client:
            with pytest.raises(NodeExecutionError, match="exceeded"):
                await execute_http_node(
                    node, {}, timeout_seconds=5.0, max_response_bytes=8, client=client
                )


async def test_http_internal_allowlist_pins_dns_and_preserves_host(monkeypatch):
    import asyncio

    calls = []

    async def resolve(host, port, **kwargs):
        calls.append(host)
        return [(0, 0, 0, "", ("10.2.3.4" if len(calls) == 1 else "127.0.0.1", port))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

    node = HTTPNode.model_validate(
        {"id": "call", "type": "http", "url": "http://sibling:8000", "output_key": "out"}
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await execute_http_node(
            node,
            {},
            timeout_seconds=5,
            max_response_bytes=100,
            client=client,
            internal_host_allowlist=frozenset({"sibling"}),
        )
    assert result == {"out": "ok"}
    assert calls == ["sibling"]
    assert requests[0].url.host == "10.2.3.4"
    assert requests[0].headers["host"] == "sibling:8000"


async def test_http_unlisted_internal_host_rejected(monkeypatch):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(0, 0, 0, "", ("10.2.3.4", 80))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    node = HTTPNode.model_validate(
        {"id": "call", "type": "http", "url": "http://evil.sibling", "output_key": "out"}
    )
    with pytest.raises(NodeExecutionError, match="unsafe"):
        await execute_http_node(
            node,
            {},
            timeout_seconds=5,
            max_response_bytes=100,
            internal_host_allowlist=frozenset({"sibling"}),
        )


async def test_http_rejects_compressed_response(monkeypatch):
    async def resolve(host, port, *, allow_internal=False):
        return "8.8.8.8"

    monkeypatch.setattr("core.nodes.http_tool.resolve_safe_address", resolve)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-encoding": "gzip"}, content=gzip.compress(b"data")
        )
    )
    node = HTTPNode.model_validate(
        {"id": "call", "type": "http", "url": "https://example.com", "output_key": "out"}
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NodeExecutionError, match="compressed"):
            await execute_http_node(
                node, {}, timeout_seconds=5, max_response_bytes=5, client=client
            )


async def test_http_stream_stops_at_limit_and_closes(monkeypatch):
    async def resolve(host, port, *, allow_internal=False):
        return "8.8.8.8"

    class Chunks(httpx.AsyncByteStream):
        def __init__(self):
            self.reads = 0
            self.closed = False

        async def __aiter__(self):
            for _ in range(10):
                self.reads += 1
                yield b"abcd"

        async def aclose(self):
            self.closed = True

    monkeypatch.setattr("core.nodes.http_tool.resolve_safe_address", resolve)
    stream = Chunks()
    transport = httpx.MockTransport(lambda request: httpx.Response(500, stream=stream))
    node = HTTPNode.model_validate(
        {"id": "call", "type": "http", "url": "https://example.com", "output_key": "out"}
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NodeExecutionError, match="exceeded"):
            await execute_http_node(
                node, {}, timeout_seconds=5, max_response_bytes=5, client=client
            )
    assert stream.reads == 2
    assert stream.closed


def test_transform_pick_const_merge():
    pick = TransformNode.model_validate(
        {
            "id": "p",
            "type": "transform",
            "operations": [{"op": "pick", "from_key": "a", "path": "$.b"}],
        }
    )
    assert execute_transform_node(pick, {"a": {"b": 1}}) == {"b": 1}

    const = TransformNode.model_validate(
        {"id": "c", "type": "transform", "operations": [{"op": "const", "value": [1, 2]}]}
    )
    assert execute_transform_node(const, {}) == {"value": [1, 2]}

    merge = TransformNode.model_validate(
        {
            "id": "m",
            "type": "transform",
            "operations": [{"op": "merge", "keys": ["x", "y"]}],
            "output_key": "merged",
        }
    )
    assert execute_transform_node(merge, {"x": {"a": 1}, "y": {"b": 2}}) == {
        "merged": {"a": 1, "b": 2}
    }
