from __future__ import annotations

from generate_openapi import main


def test_generate_openapi() -> None:
    output_path = main()

    assert output_path.exists()
    assert output_path.name == "openai-wrapper-service.openapi.json"
    assert '"OpenAI Wrapper Service"' in output_path.read_text()
