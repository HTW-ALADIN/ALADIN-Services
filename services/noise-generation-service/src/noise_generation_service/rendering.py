from __future__ import annotations

import html
import json
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field

from noise_generation_service.generator import NoiseRequest


class GridResponse(BaseModel):
    width: int
    height: int
    seed: int
    min: float
    max: float
    values: list[list[float]] = Field(description="Row-major normalized scalar values in the range 0..1.")


class ContourSvgResponse(BaseModel):
    svg: str


@dataclass(frozen=True)
class SamplePoint:
    x: float
    y: float
    value: float


_PALETTE = [
    "#1a9f0a",
    "#4fc20c",
    "#9ada11",
    "#d3e21b",
    "#f1db2d",
    "#edc05b",
    "#e8a77d",
    "#e8bca8",
]


def grid_to_response(grid: np.ndarray, request: NoiseRequest) -> GridResponse:
    return GridResponse(
        width=request.width,
        height=request.height,
        seed=request.seed,
        min=float(grid.min()),
        max=float(grid.max()),
        values=np.round(grid, 6).tolist(),
    )


def grid_to_json(grid: np.ndarray, request: NoiseRequest) -> str:
    return json.dumps(grid_to_response(grid, request).model_dump(), indent=2)


def _color_for_value(value: float, levels: int) -> str:
    band = min(levels - 1, max(0, int(value * levels)))
    palette_index = round(band * (len(_PALETTE) - 1) / max(levels - 1, 1))
    return _PALETTE[palette_index]


def _sample_points(grid: np.ndarray, count: int, seed: int) -> list[SamplePoint]:
    if count <= 0:
        return []

    rng = np.random.default_rng(seed)
    height, width = grid.shape
    xs = rng.integers(0, width, size=count)
    ys = rng.integers(0, height, size=count)
    return [SamplePoint(float(x), float(y), float(grid[y, x])) for x, y in zip(xs, ys)]


def render_contour_svg(grid: np.ndarray, request: NoiseRequest) -> ContourSvgResponse:
    cell = 4
    plot_width = request.width * cell
    plot_height = request.height * cell
    samples = _sample_points(grid, request.samplePoints, request.seed)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{plot_width}" height="{plot_height}" '
        f'viewBox="0 0 {plot_width} {plot_height}" role="img">',
        "<title>Procedural noise contour plot</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    rounded = np.round(grid * request.levels) / request.levels
    for y in range(request.height):
        for x in range(request.width):
            color = _color_for_value(float(rounded[y, x]), request.levels)
            parts.append(f'<rect x="{x * cell}" y="{y * cell}" width="{cell}" height="{cell}" fill="{color}"/>')

    parts.append('<g fill="none" stroke="#4f4f4f" stroke-width="0.6" stroke-opacity="0.55">')
    for band in range(1, request.levels):
        threshold = band / request.levels
        for y in range(request.height - 1):
            for x in range(request.width - 1):
                current = grid[y, x] >= threshold
                if current != (grid[y, x + 1] >= threshold):
                    px = (x + 1) * cell
                    parts.append(f'<line x1="{px}" y1="{y * cell}" x2="{px}" y2="{(y + 1) * cell}"/>')
                if current != (grid[y + 1, x] >= threshold):
                    py = (y + 1) * cell
                    parts.append(f'<line x1="{x * cell}" y1="{py}" x2="{(x + 1) * cell}" y2="{py}"/>')
    parts.append("</g>")

    if samples:
        parts.append('<g font-family="monospace" font-size="8" fill="#222" stroke="#222">')
        for index, point in enumerate(samples, start=1):
            cx = point.x * cell + cell / 2
            cy = point.y * cell + cell / 2
            label = html.escape(str(index))
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" fill="#f8f8f8" stroke="#222"/>')
            parts.append(f'<text x="{cx + 5:.1f}" y="{cy - 5:.1f}">{label}</text>')
        parts.append("</g>")

    parts.append("</svg>")
    return ContourSvgResponse(svg="\n".join(parts))
