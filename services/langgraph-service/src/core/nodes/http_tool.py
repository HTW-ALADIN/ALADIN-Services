"""Generic HTTP tool node for calling sibling ALADIN services."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from core.dsl import HTTPNode
from core.errors import NodeExecutionError
from core.nodes.template import render_template
from core.url_safety import UnsafeUrlError, assert_safe_url, resolve_safe_address


async def execute_http_node(
    node: HTTPNode,
    state: dict[str, Any],
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    internal_host_allowlist: frozenset[str] = frozenset(),
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Run one `http` node; returns `{output_key: parsed_body}` for the state update."""
    try:
        assert_safe_url(node.url)
    except UnsafeUrlError as exc:
        raise NodeExecutionError(node.id, f"unsafe http node URL: {exc}") from exc

    timeout = node.timeout_ms / 1000.0 if node.timeout_ms is not None else timeout_seconds
    url = httpx.URL(node.url)
    try:
        address = await asyncio.wait_for(
            resolve_safe_address(
                url.host,
                url.port or (443 if url.scheme == "https" else 80),
                allow_internal=url.host.lower().rstrip(".") in internal_host_allowlist,
            ),
            timeout=timeout,
        )
    except (UnsafeUrlError, TimeoutError) as exc:
        raise NodeExecutionError(node.id, f"unsafe http node URL: {exc}") from exc

    headers = httpx.Headers({"Content-Type": "application/json", **node.headers})
    headers["Host"] = url.netloc.decode("ascii")
    headers["Accept-Encoding"] = "identity"
    params = dict(node.query_params or {})
    body = render_template(node.body_template, state) if node.body_template is not None else None

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout, trust_env=False)
    try:
        try:
            async with http.stream(
                node.method,
                url.copy_with(host=address),
                headers=headers,
                params=params,
                json=body,
                timeout=timeout,
                follow_redirects=False,
                extensions={"sni_hostname": url.host},
            ) as response:
                encoding = response.headers.get("content-encoding", "identity").lower().strip()
                if encoding != "identity":
                    raise NodeExecutionError(node.id, "http tool returned compressed response")
                raw = bytearray()
                async for chunk in response.aiter_raw():
                    if len(raw) + len(chunk) > max_response_bytes:
                        raise NodeExecutionError(
                            node.id,
                            f"http tool response exceeded {max_response_bytes} bytes",
                            response.status_code,
                        )
                    raw.extend(chunk)
                if response.status_code >= 400:
                    text = bytes(raw).decode(response.encoding or "utf-8", errors="replace")
                    raise NodeExecutionError(
                        node.id,
                        f"http tool returned {response.status_code}: {text[:500]}",
                        response.status_code,
                    )
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        parsed: Any = json.loads(raw)
                    except ValueError as exc:
                        raise NodeExecutionError(
                            node.id, f"http tool returned invalid JSON: {exc}"
                        ) from exc
                else:
                    parsed = bytes(raw).decode(response.encoding or "utf-8", errors="replace")
                return {node.output_key: parsed}
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise NodeExecutionError(node.id, f"http tool request failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()
