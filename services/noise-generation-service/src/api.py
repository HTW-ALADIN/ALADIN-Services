from __future__ import annotations

from fastapi import FastAPI, Response

from noise_generation_service.generator import NoiseRequest, generate_noise_grid
from noise_generation_service.rendering import GridResponse, grid_to_response, render_contour_svg

app = FastAPI(
    title="Noise Generation Service",
    description=(
        "Deterministic procedural noise API for random scalar fields and contour-style plots. "
        "Designed as a REST and CLI wrapper around an embeddable noise generator."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/noise/grid",
    response_model=GridResponse,
    tags=["Noise"],
    summary="Generate a deterministic procedural noise grid",
)
def noise_grid(request: NoiseRequest) -> GridResponse:
    grid = generate_noise_grid(request)
    return grid_to_response(grid, request)


@app.post(
    "/noise/contour.svg",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {"schema": {"type": "string"}}}}},
    tags=["Noise"],
    summary="Generate a contour-style SVG plot from a deterministic procedural noise grid",
)
def contour_svg(request: NoiseRequest) -> Response:
    grid = generate_noise_grid(request)
    payload = render_contour_svg(grid, request)
    return Response(content=payload.svg, media_type="image/svg+xml")
