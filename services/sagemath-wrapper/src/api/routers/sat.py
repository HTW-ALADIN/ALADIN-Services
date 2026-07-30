from fastapi import APIRouter

from src.api.schemas.sat import SatSolveRequest, SatSolveResponse
from src.core.sat import solve_cnf

router = APIRouter(prefix="/v1/sat", tags=["sat"])


@router.post("/solve", response_model=SatSolveResponse)
def sat_solve(body: SatSolveRequest):
    return solve_cnf(body.clauses, solver=body.solver)