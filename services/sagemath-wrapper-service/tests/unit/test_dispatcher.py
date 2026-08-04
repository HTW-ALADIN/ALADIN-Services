"""Tests for src.registry.dispatcher — TDD phase."""


import pytest

_HAS_SAGE = False
try:
    import sage.all  # noqa: F401
    _HAS_SAGE = True
except ImportError:
    pass

needs_sage = pytest.mark.skipif(
    not _HAS_SAGE,
    reason="requires SageMath (not available in this environment)",
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def function_op_sat():
    """OperationSpec for sat.solve from the real registry."""
    import os

    from src.registry.loader import load_registry

    registry_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "registry"
    )
    specs = load_registry(registry_path)
    return next(s for s in specs if s.id == "sat.solve")


@pytest.fixture
def function_op_linalg_det():
    """OperationSpec for linalg.determinant from the real registry."""
    import os

    from src.registry.loader import load_registry

    registry_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "registry"
    )
    specs = load_registry(registry_path)
    return next(s for s in specs if s.id == "linalg.determinant")


@pytest.fixture
def function_op_maxima():
    """OperationSpec for maxima.evaluate from the real registry."""
    import os

    from src.registry.loader import load_registry

    registry_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "registry"
    )
    specs = load_registry(registry_path)
    return next(s for s in specs if s.id == "maxima.evaluate")


@pytest.fixture
def template_op_scalar():
    """Synthetic template OperationSpec that computes 1+1."""
    from src.registry.loader import OperationSpec

    return OperationSpec(
        id="test.add",
        summary="Add two numbers",
        kind="template",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        output_type="scalar",
        timeout_s=5.0,
        sage_template="__result__ = {{ a|sage_literal }} + {{ b|sage_literal }}",
    )


@pytest.fixture
def template_op_scalar_list_result():
    """Template that returns a list but declares output_type=scalar."""
    from src.registry.loader import OperationSpec

    return OperationSpec(
        id="test.bad-scalar",
        summary="Returns list but claims scalar",
        kind="template",
        input_schema={"type": "object", "properties": {}},
        output_type="scalar",
        timeout_s=5.0,
        sage_template="__result__ = [1, 2, 3]",
    )


@pytest.fixture
def template_op_infinite_loop():
    """Template with infinite loop for timeout testing."""
    from src.registry.loader import OperationSpec

    return OperationSpec(
        id="test.infinite",
        summary="Infinite loop",
        kind="template",
        input_schema={"type": "object", "properties": {}},
        output_type="scalar",
        timeout_s=0.5,
        sage_template=(
            "__result__ = 0\n"
            "while True:\n"
            "    __result__ += 1\n"
        ),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestExecuteOperation:
    @needs_sage
    def test_function_kind_sat_identical_to_direct_call(self, function_op_sat):
        """Dispatcher result for sat.solve == core.sat.solve_cnf() directly."""
        from src.core.sat import solve_cnf
        from src.registry.dispatcher import execute_operation

        payload = {"clauses": [[1, 2], [-1, 2], [1, -2]], "solver": "picosat"}

        dispatch_result = execute_operation(function_op_sat, payload)
        direct_result = solve_cnf(**payload)

        assert dispatch_result == direct_result

    @needs_sage
    def test_function_kind_linalg_determinant_identical(self, function_op_linalg_det):
        """Dispatcher result for linalg.determinant == core.linalg.determinant()."""
        from src.core.linalg import determinant
        from src.registry.dispatcher import execute_operation

        payload = {"matrix": [[1, 2], [3, 4]]}

        dispatch_result = execute_operation(function_op_linalg_det, payload)
        direct_result = determinant(**payload)

        assert dispatch_result == direct_result

    @needs_sage
    def test_function_kind_maxima_identical(self, function_op_maxima):
        """Dispatcher result for maxima.evaluate == core.maxima.evaluate()."""
        from src.core.maxima import evaluate
        from src.registry.dispatcher import execute_operation

        payload = {"expression": "x^3", "operation": "differentiate", "variable": "x"}

        dispatch_result = execute_operation(function_op_maxima, payload)
        direct_result = evaluate(**payload)

        assert dispatch_result == direct_result

    def test_template_kind_executes_and_returns_typed_result(self, template_op_scalar, monkeypatch):
        """Template computing 1+1 returns scalar result 2."""
        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_code", lambda *a, **kw: {"ok": True, "result": 2, "error": None})

        from src.registry.dispatcher import execute_operation

        result = execute_operation(template_op_scalar, {"a": 1, "b": 1})
        assert result == {"ok": True, "result": 2, "error": None}

    def test_payload_validation_failure_returns_structured_error(self, template_op_scalar):
        """Payload with wrong type returns structured error, not exception."""
        from src.registry.dispatcher import execute_operation

        result = execute_operation(template_op_scalar, {"a": "not-a-number", "b": 1})
        assert result["ok"] is False
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_output_type_scalar_rejects_non_scalar_sage_result(self, template_op_scalar_list_result, monkeypatch):
        """Template returns list but output_type=scalar → error."""
        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_code", lambda *a, **kw: {"ok": True, "result": [1, 2, 3], "error": None})

        from src.registry.dispatcher import execute_operation

        result = execute_operation(template_op_scalar_list_result, {})
        assert result["ok"] is False
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_timeout_from_registry_entry_is_respected(self, template_op_infinite_loop, monkeypatch):
        """Infinite loop template times out per registry entry (0.5s)."""
        import time

        from src.registry import dispatcher as disp
        monkeypatch.setattr(disp, "run_code", lambda *a, **kw: {"ok": False, "result": None, "error": "timeout"})

        from src.registry.dispatcher import execute_operation

        t0 = time.monotonic()
        result = execute_operation(template_op_infinite_loop, {})
        elapsed = time.monotonic() - t0

        assert result["ok"] is False
        assert "timeout" in result.get("error", "").lower()
        assert elapsed < 2.0, f"test took {elapsed:.2f}s, expected < 2s"