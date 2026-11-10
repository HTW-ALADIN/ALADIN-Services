"""Tests for src.registry.loader — TDD phase."""

import textwrap

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_FUNCTION_YAML = textwrap.dedent("""\
    - id: sat.solve
      summary: Solve a CNF SAT formula
      kind: function
      input_schema:
        type: object
        properties:
          clauses:
            type: array
          solver:
            type: string
        required: [clauses]
      output_type: sat_result
      timeout_s: 5.0
      function_ref: "src.core.sat:solve_cnf"
""")

SIMPLE_TEMPLATE_YAML = textwrap.dedent("""\
    - id: maxima.evaluate
      summary: Evaluate a symbolic expression
      kind: template
      input_schema:
        type: object
        properties:
          expression:
            type: string
        required: [expression]
      output_type: object
      timeout_s: 3.0
      sage_template: "{{ expression | safe }}"
""")


@pytest.fixture
def registry_dir(tmp_path):
    """Create a temp directory with a simple registry YAML file."""
    d = tmp_path / "registry"
    d.mkdir()
    (d / "sat.yaml").write_text(SIMPLE_FUNCTION_YAML)
    return d


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestLoadRegistry:
    def test_loads_valid_registry_file(self, registry_dir):
        """Single YAML file with function + template entries."""
        from src.registry.loader import load_registry

        # Add a template file too
        (registry_dir / "maxima.yaml").write_text(SIMPLE_TEMPLATE_YAML)

        specs = load_registry(str(registry_dir))
        assert len(specs) == 2

        # function entry
        fn = specs[0] if specs[0].kind == "function" else specs[1]
        assert fn.id == "sat.solve"
        assert fn.kind == "function"
        assert fn.function_ref == "src.core.sat:solve_cnf"
        assert fn.sage_template is None
        assert fn.timeout_s == 5.0
        assert fn.output_type == "sat_result"

        # template entry
        tmpl = specs[0] if specs[0].kind == "template" else specs[1]
        assert tmpl.id == "maxima.evaluate"
        assert tmpl.kind == "template"
        assert tmpl.sage_template is not None
        assert tmpl.function_ref is None
        assert tmpl.timeout_s == 3.0
        assert tmpl.output_type == "object"

    def test_duplicate_id_across_files_raises(self, registry_dir):
        """Two files with the same id raises ValueError."""
        from src.registry.loader import load_registry

        (registry_dir / "sat2.yaml").write_text(SIMPLE_FUNCTION_YAML)

        with pytest.raises(ValueError, match="sat\\.solve"):
            load_registry(str(registry_dir))

    def test_function_entry_without_function_ref_raises(self, registry_dir):
        """kind=function but no function_ref raises ValueError."""
        from src.registry.loader import load_registry

        bad = textwrap.dedent("""\
            - id: bad.func
              summary: Missing function_ref
              kind: function
              input_schema: {type: object}
              output_type: scalar
              timeout_s: 1.0
        """)
        (registry_dir / "bad.yaml").write_text(bad)

        with pytest.raises(ValueError, match="function_ref"):
            load_registry(str(registry_dir))

    def test_template_entry_without_sage_template_raises(self, registry_dir):
        """kind=template but no sage_template raises ValueError."""
        from src.registry.loader import load_registry

        bad = textwrap.dedent("""\
            - id: bad.template
              summary: Missing sage_template
              kind: template
              input_schema: {type: object}
              output_type: object
              timeout_s: 1.0
        """)
        (registry_dir / "bad.yaml").write_text(bad)

        with pytest.raises(ValueError, match="sage_template"):
            load_registry(str(registry_dir))

    def test_function_ref_must_point_to_existing_importable_function(self, registry_dir, monkeypatch):
        """Lazy mode warns (not raises); strict mode raises ValueError."""
        from src.registry.loader import load_registry

        bad = textwrap.dedent("""\
            - id: nonexistent.op
              summary: Points to nowhere
              kind: function
              input_schema: {type: object}
              output_type: scalar
              timeout_s: 1.0
              function_ref: "src.core.does_not_exist:foo"
        """)
        (registry_dir / "bad.yaml").write_text(bad)

        # Lazy mode (default): import failure is a warning, not an error
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            load_registry(str(registry_dir))
        assert any("does_not_exist" in str(x.message) for x in w)

        # Strict mode: raises ValueError
        monkeypatch.setenv("SAGE_STRICT_REGISTRY", "1")
        with pytest.raises(ValueError, match="does_not_exist"):
            load_registry(str(registry_dir))

    def test_input_schema_must_be_valid_json_schema(self, registry_dir):
        """input_schema that fails JSON Schema meta-validation raises ValueError."""
        from src.registry.loader import load_registry

        bad = textwrap.dedent("""\
            - id: bad.schema
              summary: Invalid JSON Schema
              kind: function
              input_schema: {type: "not-a-real-type"}
              output_type: scalar
              timeout_s: 1.0
              function_ref: "src.core.sat:solve_cnf"
        """)
        (registry_dir / "bad.yaml").write_text(bad)

        with pytest.raises(ValueError, match="input_schema|JSON Schema"):
            load_registry(str(registry_dir))

    def test_invalid_output_type_raises(self, registry_dir):
        """output_type not in the valid set raises ValueError."""
        from src.registry.loader import load_registry

        bad = textwrap.dedent("""\
            - id: bad.output
              summary: Bad output type
              kind: function
              input_schema: {type: object}
              output_type: "not-a-known-type"
              timeout_s: 1.0
              function_ref: "src.core.sat:solve_cnf"
        """)
        (registry_dir / "bad.yaml").write_text(bad)

        with pytest.raises(ValueError, match="output_type|not-a-known-type"):
            load_registry(str(registry_dir))

    def test_registry_directory_loads_all_yaml_files(self, registry_dir):
        """Multiple YAML files in a directory are all loaded and combined."""
        from src.registry.loader import load_registry

        # Add more files
        (registry_dir / "linalg.yaml").write_text(textwrap.dedent("""\
            - id: linalg.determinant
              summary: Matrix determinant
              kind: function
              input_schema: {type: object, properties: {matrix: {type: array}}, required: [matrix]}
              output_type: scalar
              timeout_s: 5.0
              function_ref: "src.core.linalg:determinant"
        """))
        (registry_dir / "optimize.yaml").write_text(textwrap.dedent("""\
            - id: optimize.milp
              summary: MILP solver
              kind: function
              input_schema: {type: object}
              output_type: object
              timeout_s: 10.0
              function_ref: "src.core.optimize:solve_milp"
        """))

        specs = load_registry(str(registry_dir))
        ids = {s.id for s in specs}
        assert "sat.solve" in ids
        assert "linalg.determinant" in ids
        assert "optimize.milp" in ids
        assert len(specs) == 3