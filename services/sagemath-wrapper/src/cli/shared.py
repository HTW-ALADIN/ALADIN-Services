"""Shared helpers for CLI JSON parsing and printing."""

import json
import sys


def parse_json_arg(value: str, name: str):
    """Parse a JSON string argument, exiting with a clear error on failure."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON for {name}: {e}", file=sys.stderr)
        sys.exit(1)


def print_result(data):
    """Print result as pretty JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    print()