from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_grid_endpoint_returns_requested_shape() -> None:
    response = client.post("/noise/grid", json={"width": 8, "height": 6, "seed": 123})

    assert response.status_code == 200
    payload = response.json()
    assert payload["width"] == 8
    assert payload["height"] == 6
    assert len(payload["values"]) == 6
    assert len(payload["values"][0]) == 8


def test_grid_endpoint_is_deterministic_for_seed() -> None:
    request = {"width": 8, "height": 6, "seed": 123}

    first = client.post("/noise/grid", json=request)
    second = client.post("/noise/grid", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["values"] == second.json()["values"]


def test_contour_endpoint_returns_svg() -> None:
    response = client.post("/noise/contour.svg", json={"width": 8, "height": 6, "seed": 123, "samplePoints": 2})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text
    assert "<circle" in response.text
