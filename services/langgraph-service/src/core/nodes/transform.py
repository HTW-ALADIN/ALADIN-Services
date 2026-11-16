"""Pure data reshaping: no network, no expression language."""

from __future__ import annotations

from typing import Any

from core.dsl import TransformNode, lookup_path


def execute_transform_node(node: TransformNode, state: dict[str, Any]) -> dict[str, Any]:
    """Run one `transform` node; returns the state update dict.

    - `pick`: copy `$.<from_key>[.<path>]` into the update.
    - `const`: set a literal value.
    - `merge`: merge listed top-level keys' dict values.
    Results accumulate under `output_key` when set, else merge at top level.
    """
    from core.errors import DSLValidationError

    update: dict[str, Any] = {}
    for operation in node.operations:
        if operation.op == "pick":
            source_path = f"$.{operation.from_key}"
            if operation.path:
                if not operation.path.startswith("$."):
                    raise DSLValidationError(
                        f"transform path must start with '$.'; got {operation.path!r}"
                    )
                inner = operation.path[2:]
                source_path = f"{source_path}.{inner}" if inner else source_path
            value = lookup_path(state, source_path)
            key = operation.path.split(".")[-1] if operation.path else operation.from_key
            update[key] = value
        elif operation.op == "const":
            update["value"] = operation.value
        elif operation.op == "merge":
            merged: dict[str, Any] = {}
            for key in operation.keys:
                value = lookup_path(state, f"$.{key}")
                if not isinstance(value, dict):
                    raise DSLValidationError(f"merge key {key!r} is not an object")
                merged.update(value)
            update.update(merged)
        else:  # pragma: no cover - discriminated union is exhaustive
            raise DSLValidationError(f"unknown transform op {operation!r}")
    if node.output_key is not None:
        return {node.output_key: update}
    return update
