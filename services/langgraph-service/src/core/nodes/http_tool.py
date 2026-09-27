"""Generic HTTP tool node for calling sibling ALADIN services."""

from __future__ import annotations

from typing import Any

import httpx

from core.dsl import HTTPNode
from core.errors import NodeExecutionError
from core.nodes.template import render_template
from core.url_safety import UnsafeUrlError, assert_safe_url


async def execute_http_node(
    node: HTTPNode,
    state: dict[str, Any],
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Run one `http` node; returns `{output_key: parsed_body}` for the state update."""
    try:
        assert_safe_url(node.url)
    except UnsafeUrlError as exc:
        raise NodeExecutionError(node.id, f"unsafe http node URL: {exc}") from exc

    timeout = node.timeout_ms / 1000.0 if node.timeout_ms is not None else timeout_seconds
    headers = {"Content-Type": "application/json", **node.headers}
    params = dict(node.query_params or {})
    body = render_template(node.body_template, state) if node.body_template is not None else None

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await http.request(
                node.method, node.url, headers=headers, params=params, json=body
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise NodeExecutionError(node.id, f"http tool request failed: {exc}") from exc
        if response.status_code >= 400:
            raise NodeExecutionError(
                node.id,
                f"http tool returned {response.status_code}: {response.text[:500]}",
                response.status_code,
            )
        raw = await response.aread() if hasattr(response, "aread") else response.content
        if raw is not None and len(raw) > max_response_bytes:
            raise NodeExecutionError(
                node.id,
                f"http tool response exceeded {max_response_bytes} bytes",
                response.status_code,
            )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                parsed: Any = response.json()
            except ValueError as exc:
                raise NodeExecutionError(
                    node.id, f"http tool returned invalid JSON: {exc}"
                ) from exc
        else:
            parsed = response.text
        return {node.output_key: parsed}
    finally:
        if owns_client:
            await http.aclose()
