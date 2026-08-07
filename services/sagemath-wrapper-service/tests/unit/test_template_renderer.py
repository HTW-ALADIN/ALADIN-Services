"""Tests for template rendering — now in src.registry.dispatcher."""

import ast
import textwrap

import pytest

# ── Tests ─────────────────────────────────────────────────────────────────────


class TestTemplateRenderer:
    def test_renders_simple_matrix_substitution(self):
        """Template with Matrix({{ matrix|sage_literal }}) renders correctly."""
        from src.registry.dispatcher import render_template

        template = textwrap.dedent("""\
            A = Matrix({{ matrix|sage_literal }})
            __result__ = A.determinant()
        """)
        values = {"matrix": [[1, 2], [3, 4]]}
        result = render_template(template, values)

        # Must contain a syntactically correct Python list representation
        assert "Matrix([[1, 2], [3, 4]])" in result

    def test_string_value_is_quoted_not_injected_as_code(self):
        """String values appear in quotes, not as raw tokens."""
        from src.registry.dispatcher import render_template

        template = textwrap.dedent("""\
            var('{{ name|sage_literal }}')
            __result__ = var
        """)
        values = {"name": "x"}
        result = render_template(template, values)

        # Must contain the quoted string, not the bare token 'x'
        assert "'x'" in result or '"x"' in result

    def test_injection_attempt_via_string_value_is_neutralized(self):
        """Malicious string value is repr'd — no breakout possible."""
        from src.registry.dispatcher import render_template

        template = "x = {{ name|sage_literal }}"
        values = {
            "name": "x'); import os; os.system('rm -rf /'); print('"
        }
        result = render_template(template, values)

        # The result must be a single valid Python expression that ast can
        # parse — the injection attempt must be fully contained in a string
        # constant, not creating additional statements
        parsed = ast.parse(result, mode="exec")
        assert len(parsed.body) == 1, (
            f"Expected exactly 1 statement, got {len(parsed.body)}"
        )
        assign = parsed.body[0]
        assert isinstance(assign, ast.Assign), "Expected an assignment"
        const = assign.value
        assert isinstance(const, ast.Constant) and isinstance(const.value, str), (
            f"Expected a string constant, got {type(const).__name__}"
        )
        # The malicious payload must be fully inside the string, not escaped
        assert "rm -rf" in const.value

    def test_sandboxed_environment_blocks_attribute_access_exploits(self):
        """SandboxedEnvironment blocks '__class__.__mro__' access in templates."""
        from src.registry.dispatcher import render_template

        template = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
        values = {}

        with pytest.raises((RuntimeError, TypeError, Exception)):
            render_template(template, values)

    def test_unknown_placeholder_in_values_raises(self):
        """Missing key in values raises ValueError (StrictUndefined)."""
        from src.registry.dispatcher import render_template

        template = "x = {{ unknown_key }}; __result__ = x"
        values = {}

        with pytest.raises(ValueError):
            render_template(template, values)

    def test_extra_unused_values_are_ignored_not_error(self):
        """Extra keys in values do not cause errors."""
        from src.registry.dispatcher import render_template

        template = "x = {{ a|sage_literal }}; __result__ = x"
        values = {"a": 42, "b": "unused", "c": [1, 2, 3]}
        result = render_template(template, values)

        assert "42" in result

    def test_nested_matrix_with_floats_and_negative_numbers(self):
        """Floats, negatives, nested lists roundtrip via ast.literal_eval."""
        from src.registry.dispatcher import render_template

        template = "M = {{ matrix|sage_literal }}; __result__ = M"
        values = {"matrix": [[1.5, -2], [0, 3.333333]]}
        result = render_template(template, values)

        # Extract the value after "M = "
        # The rendered form should be parseable back to the same structure
        tree = ast.parse(result, mode="exec")
        # Find the assignment to M
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "M":
                        roundtrip = ast.literal_eval(node.value)
                        assert roundtrip == [[1.5, -2], [0, 3.333333]]
                        return
        pytest.fail("Could not find assignment to 'M' in rendered output")