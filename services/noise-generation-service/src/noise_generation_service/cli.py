from __future__ import annotations

import argparse
import sys
from pathlib import Path

from noise_generation_service.generator import NoiseRequest, generate_noise_grid
from noise_generation_service.rendering import grid_to_json, render_contour_svg


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scale", type=float, default=32.0)
    parser.add_argument("--octaves", type=int, default=4)
    parser.add_argument("--persistence", type=float, default=0.5)
    parser.add_argument("--lacunarity", type=float, default=2.0)
    parser.add_argument("--levels", type=int, default=10)
    parser.add_argument("--sample-points", type=int, default=0)
    parser.add_argument("-o", "--output", type=Path)


def _request_from_args(args: argparse.Namespace) -> NoiseRequest:
    return NoiseRequest(
        width=args.width,
        height=args.height,
        seed=args.seed,
        scale=args.scale,
        octaves=args.octaves,
        persistence=args.persistence,
        lacunarity=args.lacunarity,
        levels=args.levels,
        samplePoints=args.sample_points,
    )


def _write_output(payload: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")
        return
    output.write_text(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="noise-generation",
        description="Generate deterministic procedural noise grids and contour-style SVG plots.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    grid_parser = subparsers.add_parser("grid", help="Write a JSON scalar grid.")
    _add_common_options(grid_parser)

    contour_parser = subparsers.add_parser("contour", help="Write a contour-style SVG plot.")
    _add_common_options(contour_parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    request = _request_from_args(args)
    grid = generate_noise_grid(request)

    if args.command == "grid":
        _write_output(grid_to_json(grid, request), args.output)
        return 0

    if args.command == "contour":
        _write_output(render_contour_svg(grid, request).svg, args.output)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
