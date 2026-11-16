"""Shared helpers for node execution: JSON-path templating of outbound payloads."""

from __future__ import annotations

from typing import Any

from core.dsl import lookup_path

_MAX_TEMPLATE_DEPTH = 10


def render_template(template: Any, state: dict[str, Any], _depth: int = 0) -> Any:
    """Recursively resolve `$.path` strings inside a JSON template.

    Plain strings that do not start with `$.` pass through unchanged. Dicts and
    lists are traversed; every other scalar passes through unchanged.
    """
    from core.errors import DSLValidationError

    if _depth > _MAX_TEMPLATE_DEPTH:
        raise DSLValidationError("body template is nested too deeply")
    if isinstance(template, str):
        if template.startswith("$."):
            return lookup_path(state, template)
        return template
    if isinstance(template, dict):
        return {key: render_template(value, state, _depth + 1) for key, value in template.items()}
    if isinstance(template, list):
        return [render_template(item, state, _depth + 1) for item in template]
    return template
