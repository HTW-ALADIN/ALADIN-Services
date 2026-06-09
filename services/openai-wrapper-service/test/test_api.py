from __future__ import annotations

from fastapi.testclient import TestClient

from api import app, get_service
from openai_wrapper_service.schemas import (
    GenerateRequest,
    GenerateResponse,
    TokenUsage,
)


class FakeOpenAIWrapper:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            id="resp_test",
            model=request.model or "test-response-model",
            output_text=f"generated: {request.input}",
            usage=TokenUsage(input_tokens=3, output_tokens=4, total_tokens=7),
        )


def _client() -> TestClient:
    app.dependency_overrides[get_service] = lambda: FakeOpenAIWrapper()
    return TestClient(app)


def test_health() -> None:
    response = _client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate() -> None:
    response = _client().post("/generate", json={"input": "hello", "model": "custom-model"})

    assert response.status_code == 200
    assert response.json()["model"] == "custom-model"
    assert response.json()["output_text"] == "generated: hello"
