"""Contract tests for dynamic route registration."""

import pathlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dynamic_routes import register_routes
from src.registry.loader import OperationSpec, load_registry

REGISTRY_PATH = str(
    pathlib.Path(__file__).resolve().parents[2] / "registry"
)


def _fresh_app() -> FastAPI:
    app = FastAPI(title="test")
    register_routes(app, load_registry(REGISTRY_PATH))
    return app


def _op(**overrides) -> OperationSpec:
    """Minimal OperationSpec factory."""
    base = {
        "id": "test.op",
        "summary": "Test operation",
        "kind": "function",
        "input_schema": {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]},
        "output_type": "scalar",
        "timeout_s": 5.0,
        "function_ref": "core.linalg:determinant",
    }
    base.update(overrides)
    return OperationSpec(**base)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDynamicRoutes:
    def test_all_registry_operations_get_a_route(self):
        """Every registry entry yields a matching path in app.routes."""
        app = _fresh_app()
        specs = load_registry(REGISTRY_PATH)

        # Extract paths from OpenAPI spec — handles _IncludedRouter transparently
        from fastapi.testclient import TestClient
        client = TestClient(app)
        openapi = client.get("/openapi.json").json()
        route_paths = set(openapi.get("paths", {}))

        for spec in specs:
            expected = "/v1/" + spec.id.replace(".", "/")
            assert expected in route_paths, f"missing route {expected}"

    def test_openapi_json_reflects_registry_input_schema(self):
        """OpenAPI request schema mirrors registry/linalg.yaml for determinant."""
        app = _fresh_app()
        client = TestClient(app)

        expected_path = "/v1/linalg/determinant"

        body = client.get("/openapi.json").json()
        assert expected_path in body["paths"]

        # Find the request body schema component
        post_op = body["paths"][expected_path]["post"]
        request_body = post_op.get("requestBody", {})
        ref = request_body["content"]["application/json"]["schema"]["$ref"]
        schema_name = ref.rsplit("/", 1)[-1]
        schema = body["components"]["schemas"][schema_name]

        # Registry YAML has matrix as required array of arrays of numbers
        assert "matrix" in schema["properties"]
        assert schema["required"] == ["matrix"]
        assert schema["properties"]["matrix"]["type"] == "array"
        assert schema["properties"]["matrix"]["items"]["type"] == "array"

    def test_adding_new_registry_entry_requires_no_router_code_change(self):
        """Registering a new entry at runtime exposes the endpoint immediately."""
        app = FastAPI(title="test")
        ops = load_registry(REGISTRY_PATH)
        register_routes(app, ops)
        client = TestClient(app)

        # Add a new in-memory operation and re-register
        new_op = _op(
            id="new.op",
            kind="function",
            input_schema={"type": "object", "properties": {"matrix": {"type": "array"}}, "required": ["matrix"]},
            function_ref="core.linalg:determinant",
        )
        register_routes(app, [new_op])

        # New endpoint is immediately available
        resp = client.post("/v1/new/op", json={"matrix": [[1, 2], [3, 4]]})
        assert resp.status_code in (200, 400)  # route exists (400 if un-mocked sandbox fails)

    def test_removed_hand_written_routers_no_longer_exist(self):
        """Old router files must not contain business logic anymore."""
        routers_dir = pathlib.Path(__file__).resolve().parents[2] / "src" / "api" / "routers"

        if routers_dir.exists():
            for f in routers_dir.glob("*.py"):
                content = f.read_text()
                # No core function call sites outside the dispatcher
                assert "core.sat:solve_cnf" not in content
                assert "core.linalg:determinant" not in content
                assert "core.maxima:evaluate" not in content
                assert "core.optimize:solve_milp" not in content
        else:
            # Routers dir fully deleted — also fine
            assert not routers_dir.exists()