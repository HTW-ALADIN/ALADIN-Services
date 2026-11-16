"""Gateway-backed LLM node: builds an `openai-chat` request from thread state."""

from __future__ import annotations

from typing import Any

import httpx

from core.dsl import LLMNode, lookup_path
from core.errors import NodeExecutionError
from core.nodes.template import render_template

_GATEWAY_GENERATE_PATH = "/generate"


def build_messages(node: LLMNode, state: dict[str, Any]) -> list[dict[str, str]]:
    """Build OpenAI-chat messages from a node config and the current state."""
    if node.prompt_template is not None:
        rendered = render_template(node.prompt_template, state)
        if not isinstance(rendered, str):
            raise NodeExecutionError(node.id, "prompt_template must render to a string")
        prompt = rendered
    else:
        value = lookup_path(state, f"$.{node.input_key}")
        if isinstance(value, str):
            prompt = value
        else:
            import json

            prompt = json.dumps(value)
    messages: list[dict[str, str]] = []
    if node.system:
        messages.append({"role": "system", "content": node.system})
    messages.append({"role": "user", "content": prompt})
    return messages


def build_request(node: LLMNode, state: dict[str, Any]) -> dict[str, Any]:
    """Build the gateway `POST /generate` body for an `llm` node."""
    payload: dict[str, Any] = {
        "format": "openai-chat",
        "provider": node.provider,
        "model": node.model,
        "messages": build_messages(node, state),
    }
    if node.max_output_tokens is not None:
        payload["max_tokens"] = node.max_output_tokens
    if node.temperature is not None:
        payload["temperature"] = node.temperature
    return payload


def extract_text(payload: dict[str, Any]) -> str:
    """Extract assistant text from an `openai-chat`-shaped gateway response."""
    from core.errors import NodeExecutionError as _NodeError

    try:
        choices = payload["choices"]
        content = choices[0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise _NodeError("llm", f"unexpected gateway response shape: {exc}") from exc
    if not isinstance(content, str):
        raise _NodeError("llm", "gateway returned non-string message content")
    return content


async def execute_llm_node(
    node: LLMNode,
    state: dict[str, Any],
    *,
    gateway_base_url: str,
    gateway_api_key: str,
    timeout_seconds: float,
    retry_once: bool,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Run one `llm` node; returns `{output_key: text}` for the state update."""
    if not gateway_api_key:
        raise NodeExecutionError(
            node.id,
            "LLM_GATEWAY_API_KEY is not configured; llm nodes cannot run without it",
        )
    body = build_request(node, state)
    headers = {"Authorization": f"Bearer {gateway_api_key}"}
    url = gateway_base_url.rstrip("/") + _GATEWAY_GENERATE_PATH

    attempts = 2 if retry_once else 1
    last_error: Exception | None = None
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        for _ in range(attempts):
            try:
                response = await http.post(url, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                continue
            if response.status_code in (502, 503, 504) and attempts > 1:
                last_error = NodeExecutionError(
                    node.id, f"gateway returned {response.status_code}", response.status_code
                )
                continue
            if response.status_code >= 400:
                raise NodeExecutionError(
                    node.id,
                    f"gateway returned {response.status_code}: {response.text[:500]}",
                    response.status_code,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise NodeExecutionError(node.id, f"gateway returned invalid JSON: {exc}") from exc
            try:
                text = extract_text(payload)
            except NodeExecutionError as exc:
                exc.node_id = node.id
                raise
            return {node.output_key: text}
        assert last_error is not None
        if isinstance(last_error, NodeExecutionError):
            raise last_error
        raise NodeExecutionError(node.id, f"gateway request failed: {last_error}")
    finally:
        if owns_client:
            await http.aclose()
