from __future__ import annotations

import json

from openai_wrapper_service.cli import main
from openai_wrapper_service.schemas import (
    GenerateRequest,
    GenerateResponse,
)


class FakeOpenAIWrapper:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            id="resp_cli",
            model=request.model or "test-response-model",
            output_text=request.input.upper(),
        )


def test_generate_cli_json(capsys) -> None:
    exit_code = main(["generate", "hello"], service=FakeOpenAIWrapper())

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["output_text"] == "HELLO"


def test_generate_cli_text_only(capsys) -> None:
    exit_code = main(["generate", "hello", "--text-only"], service=FakeOpenAIWrapper())

    assert exit_code == 0
    assert capsys.readouterr().out == "HELLO\n"
