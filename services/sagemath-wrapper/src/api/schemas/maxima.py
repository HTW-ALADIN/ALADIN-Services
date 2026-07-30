from pydantic import BaseModel, Field


class MaximaEvaluateRequest(BaseModel):
    expression: str = Field(..., description="Symbolic expression")
    operation: str = Field(..., description="Operation: simplify, differentiate, integrate, solve, limit, series, laplace")
    variable: str = Field(default="x", description="Variable name")
    bounds: list[float] | None = Field(default=None, description="For limit: [point]; for series: [point, order]; for integrate: [a, b]")


class MaximaEvaluateResponse(BaseModel):
    result: str | float | list | None = None
    error: str | None = None