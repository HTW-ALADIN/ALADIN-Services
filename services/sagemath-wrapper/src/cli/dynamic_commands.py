"""Dynamic CLI command registration — creates Typer subcommands from OperationSpec."""

import json
import sys
import typing

import typer

from src.registry.dispatcher import execute_operation
from src.registry.loader import OperationSpec


def _print_result(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    print()

# CLI name overrides for backward compatibility with existing tests.
_CLI_NAME_OVERRIDES = {
    "maxima.evaluate": "eval",
}


def _needs_json_parse(json_type: str) -> bool:
    return json_type in ("array", "object", "number", "integer", "boolean")


def _register_command(
    group_app: typer.Typer,
    cmd_name: str,
    op: OperationSpec,
) -> None:
    """Register a single CLI command on *group_app* for *op*."""
    properties = op.input_schema.get("properties", {}) or {}
    required = set(op.input_schema.get("required", []) or [])

    # Build parameter list
    param_names: list[str] = []
    param_help: list[str] = []
    param_defaults: list[typing.Any] = []
    needs_json: dict[str, bool] = {}

    for field_name, field_schema in properties.items():
        arg_name = field_name.replace("-", "_")
        param_names.append(arg_name)
        json_type = field_schema.get("type", "string")
        needs_parse = _needs_json_parse(json_type)
        needs_json[arg_name] = needs_parse
        prefix = "JSON: " if needs_parse else ""
        help_text = field_schema.get("description", field_name)
        default_val = field_schema.get("default")
        param_help.append(f"{prefix}{help_text}")
        param_defaults.append(default_val)

    # Build function source
    def_lines = []
    for i, name in enumerate(param_names):
        default_val = param_defaults[i]
        hlp = param_help[i]
        if name in required:
            def_lines.append(f"    {name}=None")
        elif default_val is not None:
            def_lines.append(f"    {name}={str(default_val)!r}")
        else:
            def_lines.append(f"    {name}=None")
    def_lines.append("    spec_file=None")

    body_lines = []
    body_lines.append("    payload = {}")
    body_lines.append("    if spec_file is not None:")
    body_lines.append("        with open(spec_file) as f:")
    body_lines.append("            payload = json.load(f)")
    body_lines.append("    else:")
    for name in param_names:
        key = name.replace("_", "-")
        if needs_json.get(name):
            body_lines.append(f"        if {name} is not None:")
            body_lines.append(f"            payload[{key!r}] = json.loads({name})")
        else:
            body_lines.append(f"        if {name} is not None:")
            body_lines.append(f"            payload[{key!r}] = {name}")
    for field_name in sorted(required):
        body_lines.append(f"    if {field_name!r} not in payload:")
        body_lines.append(f"        print(f'Error: missing required --{field_name}', file=sys.stderr)")
        body_lines.append("        raise typer.Exit(2)")
    body_lines.append("    result = execute_operation(op, payload)")
    body_lines.append("    if not result['ok']:")
    body_lines.append("        print(f\"Error: {result['error']}\", file=sys.stderr)")
    body_lines.append("        raise typer.Exit(1)")
    body_lines.append('    _print_result(result["result"])')

    func_source = "def _handler(\n" + ",\n".join(def_lines) + "\n):\n" + "\n".join("    " + l for l in body_lines)

    ns: dict = {
        "json": json, "sys": sys, "typer": typer,
        "execute_operation": execute_operation,
        "op": op, "_print_result": _print_result,
    }
    exec(func_source, ns)  # noqa: S102
    fn = ns["_handler"]

    # Replace with Typer Options
    import inspect
    sig_params = []
    for i, name in enumerate(param_names):
        hlp = param_help[i]
        if name in required:
            opt = typer.Option(None, help=hlp)
        elif param_defaults[i] is not None:
            opt = typer.Option(str(param_defaults[i]), help=hlp)
        else:
            opt = typer.Option(None, help=hlp)
        sig_params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=opt))
    sig_params.append(inspect.Parameter("spec_file", inspect.Parameter.KEYWORD_ONLY, default=typer.Option(None, help="JSON spec file")))
    fn.__signature__ = inspect.Signature(sig_params)

    fn.__name__ = cmd_name
    fn.__qualname__ = cmd_name
    group_app.command(name=cmd_name, help=op.summary)(fn)


def register_commands(app: typer.Typer, operations: list[OperationSpec]) -> None:
    """Register CLI subcommands for every *operations* on *app*."""
    groups: dict[str, typer.Typer] = {}

    for op in operations:
        parts = op.id.split(".", 1)
        group_name = parts[0]
        cmd_name = _CLI_NAME_OVERRIDES.get(op.id, parts[1] if len(parts) > 1 else op.id)
        if group_name not in groups:
            group_app = typer.Typer()
            groups[group_name] = group_app
            app.add_typer(group_app, name=group_name, help=group_name)
        _register_command(groups[group_name], cmd_name, op)