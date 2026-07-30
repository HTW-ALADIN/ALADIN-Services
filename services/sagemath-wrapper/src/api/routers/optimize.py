from fastapi import APIRouter

from src.api.schemas.optimize import (
    FindRootRequest,
    MilpRequest,
    MilpResponse,
    MinimizeRequest,
)
from src.core.optimize import find_root, minimize, solve_milp

router = APIRouter(prefix="/v1/optimize", tags=["optimize"])


@router.post("/milp", response_model=MilpResponse)
def milp_endpoint(body: MilpRequest):
    return solve_milp(
        body.variables, body.objective, body.maximize,
        [c.model_dump() for c in body.constraints],
        var_types=body.var_types, solver=body.solver,
    )


@router.post("/find-root", response_model=MilpResponse)
def find_root_endpoint(body: FindRootRequest):
    return find_root(body.expression, body.variable, body.a, body.b)


@router.post("/minimize", response_model=MilpResponse)
def minimize_endpoint(body: MinimizeRequest):
    return minimize(body.expression, body.variables, body.x0)