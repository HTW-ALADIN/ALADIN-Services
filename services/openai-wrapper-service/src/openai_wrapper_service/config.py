import os


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    return value or None


def openai_client_options() -> dict[str, object]:
    options: dict[str, object] = {
        "timeout": float(os.getenv("OPENAI_WRAPPER_TIMEOUT_SECONDS", "60")),
        "max_retries": int(os.getenv("OPENAI_WRAPPER_MAX_RETRIES", "2")),
    }
    for option_name, env_name in {
        "api_key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "organization": "OPENAI_ORG_ID",
        "project": "OPENAI_PROJECT_ID",
    }.items():
        value = _env_value(env_name)
        if value is not None:
            options[option_name] = value
    return options
