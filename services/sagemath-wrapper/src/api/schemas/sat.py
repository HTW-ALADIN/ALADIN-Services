from pydantic import BaseModel, Field


class SatSolveRequest(BaseModel):
    clauses: list[list[int]] = Field(..., description="DIMACS CNF clauses")
    solver: str = Field(default="picosat", description="SAT solver name")


class SatSolveResponse(BaseModel):
    satisfiable: bool
    assignment: dict | None = None
    solver: str