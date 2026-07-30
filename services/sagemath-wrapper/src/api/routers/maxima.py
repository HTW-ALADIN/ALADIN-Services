from fastapi import APIRouter

from src.api.schemas.maxima import MaximaEvaluateRequest, MaximaEvaluateResponse
from src.core.maxima import evaluate

router = APIRouter(prefix="/v1/maxima", tags=["maxima"])


@router.post("/evaluate", response_model=MaximaEvaluateResponse)
def maxima_evaluate(body: MaximaEvaluateRequest):
    return evaluate(body.expression, body.operation, variable=body.variable, bounds=body.bounds)