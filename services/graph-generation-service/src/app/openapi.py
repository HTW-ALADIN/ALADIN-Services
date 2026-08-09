from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.catalog import ALGORITHM_SCHEMAS

Schema = dict[str, Any]


def install_openapi_schema(app: FastAPI) -> None:
    def custom_openapi() -> Schema:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        _patch_graph_generation_operation(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    setattr(app, "openapi", custom_openapi)


def _patch_graph_generation_operation(schema: Schema) -> None:
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.update(_public_request_components())
    _strip_internal_backend_discriminators(components)

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)

    operation = schema["paths"]["/v1/graphs"]["post"]
    operation["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/GraphGenerationRequest"
    }
    operation["responses"]["400"] = {
        "description": "Request validation failed.",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"},
            },
        },
    }


def _public_request_components() -> dict[str, Schema]:
    components: dict[str, Schema] = {
        "GraphGenerationRequest": {
            "oneOf": [
                {"$ref": f"#/components/schemas/{schema_name}"} for schema_name, _variants in ALGORITHM_SCHEMAS.values()
            ],
            "discriminator": {
                "propertyName": "algorithm",
                "mapping": {
                    algorithm: f"#/components/schemas/{schema_name}"
                    for algorithm, (schema_name, _variants) in ALGORITHM_SCHEMAS.items()
                },
            },
        },
    }

    for algorithm, (schema_name, variants) in ALGORITHM_SCHEMAS.items():
        if len(variants) == 1:
            backend, params_schema = variants[0]
            components[schema_name] = _request_variant(
                algorithm=algorithm,
                backend=backend,
                params_ref=f"#/components/schemas/{params_schema}",
                title=schema_name,
            )
            continue

        components[schema_name] = {
            "oneOf": [
                {"$ref": (f"#/components/schemas/{_variant_schema_name(schema_name=schema_name, backend=backend)}")}
                for backend, _params_schema in variants
            ],
            "discriminator": {
                "propertyName": "backend",
                "mapping": {
                    backend: (f"#/components/schemas/{_variant_schema_name(schema_name=schema_name, backend=backend)}")
                    for backend, _params_schema in variants
                },
            },
        }

        for backend, params_schema in variants:
            variant_schema = _variant_schema_name(schema_name=schema_name, backend=backend)
            components[variant_schema] = _request_variant(
                algorithm=algorithm,
                backend=backend,
                params_ref=f"#/components/schemas/{params_schema}",
                title=variant_schema,
            )

    return components


def _strip_internal_backend_discriminators(components: dict[str, Schema]) -> None:
    for component_name, component in components.items():
        if not component_name.endswith("Params"):
            continue

        properties = component.get("properties")
        if not isinstance(properties, dict) or "backend" not in properties:
            continue

        backend_schema = properties.get("backend")
        if not isinstance(backend_schema, dict) or "const" not in backend_schema:
            continue

        properties.pop("backend", None)
        required = component.get("required")
        if isinstance(required, list) and "backend" in required:
            required.remove("backend")


def _request_variant(*, algorithm: str, backend: str, params_ref: str, title: str) -> Schema:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["algorithm", "backend", "params"],
        "properties": {
            "algorithm": {"type": "string", "const": algorithm, "title": "Algorithm"},
            "backend": {"type": "string", "const": backend, "title": "Backend"},
            "params": {"$ref": params_ref},
            "output": {"$ref": "#/components/schemas/OutputOptions"},
        },
        "title": title,
    }


def _variant_schema_name(*, schema_name: str, backend: str) -> str:
    return f"{schema_name.removesuffix('Request')}{backend.title()}Request"
