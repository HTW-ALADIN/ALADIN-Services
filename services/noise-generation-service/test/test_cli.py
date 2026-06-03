import json
import runpy

import pytest

from noise_generation_service import cli
from noise_generation_service.cli import main


def test_cli_grid_writes_json(tmp_path) -> None:
    output = tmp_path / "grid.json"

    result = main(["grid", "--width", "4", "--height", "3", "--seed", "7", "--output", str(output)])

    assert result == 0
    payload = json.loads(output.read_text())
    assert payload["width"] == 4
    assert payload["height"] == 3


def test_cli_contour_writes_svg(tmp_path) -> None:
    output = tmp_path / "contour.svg"

    result = main(["contour", "--width", "4", "--height", "3", "--seed", "7", "--output", str(output)])

    assert result == 0
    assert output.read_text().startswith("<svg")


def test_cli_grid_writes_to_stdout(capsys) -> None:
    result = main(["grid", "--width", "4", "--height", "3", "--seed", "7"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["width"] == 4
    assert payload["height"] == 3


def test_cli_unknown_command_defensive_branch(monkeypatch) -> None:
    class Parser:
        def parse_args(self, argv):
            return type(
                "Args",
                (),
                {
                    "command": "unknown",
                    "width": 2,
                    "height": 2,
                    "seed": 0,
                    "scale": 32.0,
                    "octaves": 1,
                    "persistence": 0.5,
                    "lacunarity": 2.0,
                    "levels": 2,
                    "sample_points": 0,
                    "output": None,
                },
            )()

        def error(self, message):
            raise RuntimeError(message)

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())

    with pytest.raises(RuntimeError, match="Unknown command"):
        main([])


def test_cli_unknown_command_returns_when_parser_error_does_not_exit(monkeypatch) -> None:
    class Parser:
        def parse_args(self, argv):
            return type(
                "Args",
                (),
                {
                    "command": "unknown",
                    "width": 2,
                    "height": 2,
                    "seed": 0,
                    "scale": 32.0,
                    "octaves": 1,
                    "persistence": 0.5,
                    "lacunarity": 2.0,
                    "levels": 2,
                    "sample_points": 0,
                    "output": None,
                },
            )()

        def error(self, message):
            self.message = message

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())

    assert main([]) == 2


def test_cli_module_entrypoint(monkeypatch, tmp_path) -> None:
    output = tmp_path / "entrypoint.json"
    monkeypatch.setattr(
        "sys.argv",
        ["noise-generation", "grid", "--width", "2", "--height", "2", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("noise_generation_service.cli", run_name="__main__")

    assert exc.value.code == 0
    assert json.loads(output.read_text())["width"] == 2
