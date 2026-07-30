from pydantic import BaseModel, Field


class ConstraintModel(BaseModel):
    coeffs: dict[str, float]
    min: float | None = None
    max: float | None = None


class MilpRequest(BaseModel):
    variables: list[str]
    objective: dict[str, float]
    maximize: bool = True
    constraints: list[ConstraintModel] = Field(default_factory=list)
    var_types: dict[str, str] | None = None
    solver: str = Field(default="GLPK", description="MILP solver name")


class MilpResponse(BaseModel):
    status: str
    objective_value: float | None = None
    values: dict[str, float] | None = None
    error: str | None = None


class FindRootRequest(BaseModel):
    expression: str = Field(..., description="Symbolic expression")
    variable: str = Field(default="x", description="Variable name")
    a: float = Field(..., description="Interval start")
    b: float = Field(..., description="Interval end")


class MinimizeRequest(BaseModel):
    expression: str = Field(..., description="Symbolic expression")
    variables: list[str] = Field(..., description="Variable names")
    x0: list[float] = Field(..., description="Initial guess")
    objective_value: float | None = None
    values: dict[str, float] | None = None
    error: str | None = None