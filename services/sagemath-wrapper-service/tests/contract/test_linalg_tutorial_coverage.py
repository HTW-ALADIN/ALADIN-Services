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

    @needs_sage
    def test_eigenvalues_complex_supported(self):
        """Eigenvalues of [[0,4],[-1,0]] = [-2*I, 2*I] — complex output."""
        M = [[0, 4], [-1, 0]]
        resp = client.post("/v1/linalg/eigenvalues", json={"matrix": M})
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert len(result) == 2
        # Each eigenvalue is [real, imag]
        has_neg_2i = any(
            abs(v[0]) < 1e-9 and abs(v[1] - (-2)) < 1e-9
            if isinstance(v, list) else False
            for v in result
        )
        has_2i = any(
            abs(v[0]) < 1e-9 and abs(v[1] - 2) < 1e-9
            if isinstance(v, list) else False
            for v in result
        )
        assert has_neg_2i, f"expected -2i in {result}"
        assert has_2i, f"expected 2i in {result}"

    @needs_sage
    def test_eigenvectors_left_matches_tutorial_example(self):
        """eigenvectors_left of [[1,3],[3,1]] = [(4,[(1,1)],1), (-2,[(1,-1)],1)]."""
        B = [[1, 3], [3, 1]]
        resp = client.post("/v1/linalg/eigenvectors_left", json={"matrix": B})
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert isinstance(result, list) and len(result) == 2, f"got {result}"
        # result is [{eigenvalue, eigenvectors, multiplicity}, ...]
        eigvals = set()
        for entry in result:
            assert "eigenvalue" in entry
            assert "eigenvectors" in entry
            assert "multiplicity" in entry
            eigvals.add(entry["eigenvalue"])
        assert 4 in eigvals, f"expected eigenvalue 4 in {result}"
        assert -2 in eigvals, f"expected eigenvalue -2 in {result}"

    @needs_sage
    def test_evaluate_matrix_chain_expression(self):
        """Evaluate A*B*C*A^4 - 5*(B-C) + A.inverse() with named matrices."""
        A_val = [[1, 2], [3, 4]]
        B_val = [[5, 6], [7, 8]]
        C_val = [[1, -1], [0, 2]]
        resp = client.post("/v1/linalg/evaluate", json={
            "matrices": {"A": A_val, "B": B_val, "C": C_val},
            "expression": "A * B * C * A^4 - 5*(B - C) + A.inverse()",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert isinstance(result, list) and len(result) > 0, f"got {type(result)}: {result}"
        assert all(isinstance(row, list) for row in result), "expected matrix (list of lists)"

    @needs_sage
    def test_evaluate_with_vectors(self):
        """Evaluate a matrix-vector expression with named vectors."""
        resp = client.post("/v1/linalg/evaluate", json={
            "matrices": {"A": [[1, 2, 3], [3, 2, 1], [1, 1, 1]]},
            "vectors": {"w": [1, 1, -4]},
            "expression": "w * A",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        assert result == [0, 0, 0], f"got {result}"

    def test_evaluate_endpoint_in_openapi(self):
        """linalg.evaluate appears in OpenAPI paths."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/v1/linalg/evaluate" in paths, f"missing evaluate path in {list(paths)}"
        # The expression field should be typed as string
        post_op = paths["/v1/linalg/evaluate"]["post"]
        ref = post_op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        schema_name = ref.rsplit("/", 1)[-1]
        schema = resp.json()["components"]["schemas"][schema_name]
        assert "expression" in schema.get("properties", {}), "expression field missing"
        assert schema["properties"]["expression"]["type"] == "string", "expression not string"

    def test_evaluate_missing_expression_is_422(self):
        """evaluate without expression returns 422."""
        resp = client.post("/v1/linalg/evaluate", json={"matrices": {"A": [[1, 2], [3, 4]]}})
        assert resp.status_code == 422, resp.text

    def test_evaluate_expression_only_is_accepted(self):
        """evaluate with only expression (no matrices/vectors) is accepted."""
        # This is a valid request — the expression may be a literal like 42
        # We mock run_code to avoid actual SageMath execution
        from unittest.mock import patch

        from src.registry import dispatcher as disp

        with patch.object(disp, "run_code", return_value={"ok": True, "result": 42, "error": None}):
            resp = client.post("/v1/linalg/evaluate", json={"expression": "42"})
        assert resp.status_code == 200, resp.text

    def test_new_entries_have_typed_openapi_schema(self):
        """All new paths have concrete types in OpenAPI, not generic blobs."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]

        new_paths = [
            "/v1/linalg/kernel",
            "/v1/linalg/echelon_form",
            "/v1/linalg/rank",
            "/v1/linalg/matrix_vector_product",
            "/v1/linalg/vector_matrix_product",
            "/v1/linalg/eigenvectors_left",
            "/v1/linalg/eigenvectors_right",
            "/v1/linalg/evaluate",
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