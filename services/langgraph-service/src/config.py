"""Environment-driven configuration.

LLM credentials live in llm-gateway-service, not here: this service holds only
the gateway connection details. Graph definitions are caller-supplied JSON
(data only, never code) and graph/thread registries are ephemeral in v1.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8004
    log_level: str = "info"

    # Base URL of the llm-gateway-service API used by `llm` nodes. The gateway
    # exposes unprefixed routes (POST {base}/generate), so this must NOT carry
    # a version suffix.
    llm_gateway_base_url: str = "http://localhost:8002"
    # Bearer token for inference requests against the gateway. Required for
    # `llm` nodes (they fail fast with a clear error when unset); /health and
    # non-LLM graphs still work without it.
    llm_gateway_api_key: str = ""
    llm_node_timeout_seconds: float = 60.0
    llm_retry_once: bool = False

    http_node_timeout_seconds: float = 30.0
    max_tool_response_bytes: int = 1048576

    checkpointer: Literal["memory", "postgres"] = "memory"
    postgres_url: str = ""

    run_timeout_seconds: float = 120.0
    run_concurrency: int = 4
    recursion_limit: int = 25

    max_graph_bytes: int = 65536
    max_input_bytes: int = 262144
    max_output_bytes: int = 1048576


settings = Settings()
