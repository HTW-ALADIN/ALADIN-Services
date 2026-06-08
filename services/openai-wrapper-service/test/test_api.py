from __future__ import annotations

from fastapi.testclient import TestClient

from api import app, get_service
from openai_wrapper_service.schemas import (
    EmbeddingItem,
    EmbeddingsRequest,
    EmbeddingsResponse,
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

    def embeddings(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        inputs = request.input if isinstance(request.input, list) else [request.input]
        return EmbeddingsResponse(
            model=request.model or "test-embedding-model",
            data=[EmbeddingItem(index=index, embedding=[float(index), 1.0]) for index, _ in enumerate(inputs)],
            usage=TokenUsage(input_tokens=len(inputs), total_tokens=len(inputs)),
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


def test_embeddings() -> None:
    response = _client().post("/embeddings", json={"input": ["a", "b"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "test-embedding-model"
    assert payload["data"] == [{"index": 0, "embedding": [0.0, 1.0]}, {"index": 1, "embedding": [1.0, 1.0]}]
