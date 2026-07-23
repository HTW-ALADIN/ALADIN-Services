"""Environment-driven configuration.

Intentionally does NOT contain any provider credential settings: per the
implementation plan, credentials flow through the API/CLI request payload only,
never through service-level environment variables.
"""

import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

# Safe local-dev fallback if GRAPH_CURSOR_SECRET is unset: a random value
# generated once at import time so the service still runs, but cursors will
# stop validating across process restarts/replicas. Any real deployment must
# set GRAPH_CURSOR_SECRET explicitly to a stable secret.
_DEV_ONLY_RANDOM_SECRET = secrets.token_hex(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8003
    log_level: str = "info"

    # HMAC signing key for citation-graph pagination cursors (see core/pagination.py).
    graph_cursor_secret: str = _DEV_ONLY_RANDOM_SECRET

    # Bounds a single /v1/download call; larger batches must be paginated
    # client-side across multiple calls rather than relying on a job queue.
    download_max_batch_size: int = 20

    # Bounds a single BFS level of /v1/graph expansion.
    graph_max_nodes_per_level_default: int = 100
    graph_max_total_nodes_default: int = 2000
    graph_max_depth_default: int = 2

    # Per-provider HTTP timeout (seconds).
    provider_timeout_seconds: float = 30.0


settings = Settings()
