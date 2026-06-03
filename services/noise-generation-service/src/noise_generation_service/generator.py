from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field
from pyfastnoiselite import pyfastnoiselite as fastnoise


class NoiseRequest(BaseModel):
    width: int = Field(default=128, ge=2, le=512, description="Grid width in cells.")
    height: int = Field(default=128, ge=2, le=512, description="Grid height in cells.")
    seed: int = Field(default=0, ge=0, le=2**31 - 1, description="Deterministic random seed.")
    scale: float = Field(default=32.0, gt=0.0, le=10_000.0, description="Spatial scale; larger values zoom out.")
    octaves: int = Field(default=4, ge=1, le=10, description="Number of fractal noise octaves.")
    persistence: float = Field(default=0.5, gt=0.0, le=1.0, description="Amplitude multiplier per octave.")
    lacunarity: float = Field(default=2.0, ge=1.0, le=4.0, description="Frequency multiplier per octave.")
    levels: int = Field(default=10, ge=2, le=32, description="Number of color bands in SVG contour output.")
    samplePoints: int = Field(
        default=0,
        ge=0,
        le=128,
        description="Optional number of deterministic sample points to overlay in SVG output.",
    )


def generate_noise_grid(request: NoiseRequest) -> np.ndarray:
    """Generate a normalized 2D fractal noise grid with FastNoiseLite."""

    generator = fastnoise.FastNoiseLite()
    generator.seed = request.seed
    generator.noise_type = fastnoise.NoiseType.NoiseType_Perlin
    generator.fractal_type = fastnoise.FractalType.FractalType_FBm
    generator.frequency = 1.0 / request.scale
    generator.fractal_octaves = request.octaves
    generator.fractal_gain = request.persistence
    generator.fractal_lacunarity = request.lacunarity

    x = np.arange(request.width, dtype=np.float32)
    y = np.arange(request.height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    coords = np.vstack((xx.ravel(), yy.ravel())).astype(np.float32)
    grid = generator.gen_from_coords(coords).reshape((request.height, request.width)).astype(np.float64)

    min_value = float(grid.min())
    max_value = float(grid.max())
    if max_value == min_value:
        return np.zeros_like(grid)
    return (grid - min_value) / (max_value - min_value)
