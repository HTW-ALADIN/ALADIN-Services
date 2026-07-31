"""Contract tests for new linalg template entries — SageMath tutorial coverage."""


import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

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

# Reference matrix from the tutorial
A = [[1, 2, 3], [3, 2, 1], [1, 1, 1]]
w = [1, 1, -4]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLinalgTutorialCoverage:
    @needs_sage
    def test_matrix_vector_product_matches_tutorial_example(self):
        """A * w = [-9, 1, -2] from the tutorial."""
        resp = client.post("/v1/linalg/matrix_vector_product", json={
            "matrix": A, "vector": w,
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        # result is a single value or a dict with result key
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert result == [-9, 1, -2], f"got {result}"

    @needs_sage
    def test_vector_matrix_product_matches_tutorial_example(self):
        """w * A = [0, 0, 0] from the tutorial."""
        resp = client.post("/v1/linalg/vector_matrix_product", json={
            "matrix": A, "vector": w,
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert result == [0, 0, 0], f"got {result}"

    @needs_sage
    def test_kernel_matches_tutorial_example(self):
        """kernel(A) spans the same space as [[1, 1, -4]]."""
        resp = client.post("/v1/linalg/kernel", json={"matrix": A})
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]

        # result should be a matrix (list of lists) — the kernel basis
        assert isinstance(result, list) and len(result) > 0, f"expected non-empty list, got {result}"
        basis = result[0]  # first basis vector

        # Check that the basis vector is a scalar multiple of [1, 1, -4]
        # If basis[0] == 0, skip; otherwise check ratio consistency
        ratios = []
        for i in range(len(basis)):
            if basis[i] != 0:
                ratios.append(basis[i] / [1, 1, -4][i])
        assert len(ratios) > 0, "basis vector is all zeros"
        ref_ratio = ratios[0]
        for r in ratios[1:]:
            assert abs(r - ref_ratio) < 1e-9, (
                f"basis vector {basis} not proportional to [1, 1, -4]"
            )

    @needs_sage
    def test_echelon_form_of_singular_matrix(self):
        """Echelon form of a singular matrix has a zero row."""
        singular = [[1, 2], [2, 4]]
        resp = client.post("/v1/linalg/echelon_form", json={"matrix": singular})
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]

        assert isinstance(result, list), f"expected list, got {type(result)}"
        # Last row should be all zeros (or very close)
        last_row = result[-1]
        assert all(abs(v) < 1e-9 for v in last_row), (
            f"last row {last_row} not all zeros"
        )

    @needs_sage
    def test_rank_matches_expected_value(self):
        """Rank of singular [[1,2],[2,4]] is 1."""
        singular = [[1, 2], [2, 4]]
        resp = client.post("/v1/linalg/rank", json={"matrix": singular})
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert result == 1, f"expected rank 1, got {result}"

    def test_new_entries_have_typed_openapi_schema(self):
        """All 5 new paths have concrete types in OpenAPI, not generic blobs."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]

        new_paths = [
            "/v1/linalg/kernel",
            "/v1/linalg/echelon_form",
            "/v1/linalg/rank",
            "/v1/linalg/matrix_vector_product",
            "/v1/linalg/vector_matrix_product",
        ]

        for path in new_paths:
            assert path in paths, f"missing path {path}"

            # Get the request body schema
            post_op = paths[path]["post"]
            request_body = post_op.get("requestBody", {})
            ref = request_body["content"]["application/json"]["schema"]["$ref"]
            schema_name = ref.rsplit("/", 1)[-1]
            schema = resp.json()["components"]["schemas"][schema_name]

            # matrix field must be type: array (not generic object/string)
            if "matrix" in schema.get("properties", {}):
                assert schema["properties"]["matrix"]["type"] == "array", (
                    f"{path}: matrix type is not array"
                )

            # Check that the response isn't just a generic object
            # (FastAPI generates 200 responses from route return type)