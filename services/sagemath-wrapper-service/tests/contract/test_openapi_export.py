"""Contract tests for OpenAPI export."""

import os
import subprocess
import sys

import yaml

SCRIPT_PATH = "scripts/export_openapi.py"
OUTPUT_PATH = "openapi/openapi.yaml"

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "registry"
)


def test_openapi_export_script_produces_valid_yaml_file():
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--out", OUTPUT_PATH],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    with open(OUTPUT_PATH) as f:
        spec = yaml.safe_load(f)
    assert "openapi" in spec, "not a valid OpenAPI document"
    assert "info" in spec
    assert "paths" in spec


def test_openapi_export_contains_all_registry_operations():
    """Exported spec contains a path for EVERY registry entry (incl. M6)."""
    from src.registry.loader import load_registry

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--out", OUTPUT_PATH],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    with open(OUTPUT_PATH) as f:
        spec = yaml.safe_load(f)
    paths = spec.get("paths", {})

    registry = load_registry(REGISTRY_PATH)
    for entry in registry:
        expected = "/v1/" + entry.id.replace(".", "/")
        assert expected in paths, f"missing path {expected} for entry {entry.id}"


def test_openapi_export_contains_all_four_module_tags():
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--out", OUTPUT_PATH],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    with open(OUTPUT_PATH) as f:
        spec = yaml.safe_load(f)
    paths = spec.get("paths", {})
    assert "/v1/sat/solve" in paths
    assert "/v1/linalg/determinant" in paths
    assert "/v1/optimize/milp" in paths
    assert "/v1/maxima/evaluate" in paths