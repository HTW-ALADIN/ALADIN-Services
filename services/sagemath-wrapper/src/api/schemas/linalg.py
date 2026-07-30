from pydantic import BaseModel, Field


class MatrixRequest(BaseModel):
    matrix: list[list[float]] = Field(..., description="Square matrix")


class LinearSystemRequest(BaseModel):
    a: list[list[float]] = Field(..., description="Coefficient matrix")
    b: list[float] = Field(..., description="Right-hand side vector")


class LinalgResponse(BaseModel):
    result: list | float | None = None
    error: str | None = None