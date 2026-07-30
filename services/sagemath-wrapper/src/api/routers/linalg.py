from fastapi import APIRouter

from src.api.schemas.linalg import LinalgResponse, LinearSystemRequest, MatrixRequest
from src.core import linalg

router = APIRouter(prefix="/v1/linalg", tags=["linalg"])


@router.post("/determinant", response_model=LinalgResponse)
def det_endpoint(body: MatrixRequest):
    return linalg.determinant(body.matrix)


@router.post("/inverse", response_model=LinalgResponse)
def inv_endpoint(body: MatrixRequest):
    return linalg.inverse(body.matrix)


@router.post("/eigenvalues", response_model=LinalgResponse)
def eig_endpoint(body: MatrixRequest):
    return linalg.eigenvalues(body.matrix)


@router.post("/solve", response_model=LinalgResponse)
def solve_endpoint(body: LinearSystemRequest):
    return linalg.solve_linear_system(body.a, body.b)


@router.post("/qr", response_model=LinalgResponse)
def qr_endpoint(body: MatrixRequest):
    return linalg.qr(body.matrix)


@router.post("/lu", response_model=LinalgResponse)
def lu_endpoint(body: MatrixRequest):
    return linalg.lu(body.matrix)


@router.post("/cholesky", response_model=LinalgResponse)
def cholesky_endpoint(body: MatrixRequest):
    return linalg.cholesky(body.matrix)


@router.post("/svd", response_model=LinalgResponse)
def svd_endpoint(body: MatrixRequest):
    return linalg.svd(body.matrix)


@router.post("/matrix-exp", response_model=LinalgResponse)
def matrix_exp_endpoint(body: MatrixRequest):
    return linalg.matrix_exp(body.matrix)


@router.post("/right-kernel", response_model=LinalgResponse)
def right_kernel_endpoint(body: MatrixRequest):
    return linalg.right_kernel(body.matrix)


@router.post("/left-kernel", response_model=LinalgResponse)
def left_kernel_endpoint(body: MatrixRequest):
    return linalg.left_kernel(body.matrix)


@router.post("/charpoly", response_model=LinalgResponse)
def charpoly_endpoint(body: MatrixRequest):
    return linalg.charpoly(body.matrix)