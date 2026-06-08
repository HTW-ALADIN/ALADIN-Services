import json

import generate_openapi


def test_generate_openapi_main_writes_spec(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "src" / "generate_openapi.py"
    script_path.parent.mkdir()
    script_path.write_text("")
    monkeypatch.setattr(generate_openapi, "_src_dir", script_path.parent)

    output_path = generate_openapi.main()

    assert output_path == tmp_path / "noise-generation-service.openapi.json"
    spec = json.loads(output_path.read_text())
    assert spec["info"]["title"] == "Noise Generation Service"
    assert "/noise/grid" in spec["paths"]
