import numpy as np

from noise_generation_service import generator
from noise_generation_service.generator import NoiseRequest, generate_noise_grid


def test_generate_noise_grid_handles_constant_library_output(monkeypatch) -> None:
    class ConstantNoise:
        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

        def gen_from_coords(self, coords):
            return np.zeros(coords.shape[1], dtype=np.float32)

    monkeypatch.setattr(generator.fastnoise, "FastNoiseLite", ConstantNoise)

    grid = generate_noise_grid(NoiseRequest(width=3, height=2))

    assert grid.shape == (2, 3)
    assert np.all(grid == 0)
