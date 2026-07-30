"""SageMath Wrapper CLI — direct calls to core/* functions."""

import json
import sys

import typer

from src.cli.shared import parse_json_arg, print_result
from src.core import linalg
from src.core.maxima import evaluate
from src.core.optimize import find_root, minimize, solve_milp
from src.core.sat import solve_cnf

app = typer.Typer()
sat_app = typer.Typer()
linalg_app = typer.Typer()
optimize_app = typer.Typer()
maxima_app = typer.Typer()
app.add_typer(sat_app, name="sat", help="SAT solving commands")
app.add_typer(linalg_app, name="linalg", help="Linear algebra commands")
app.add_typer(optimize_app, name="optimize", help="Optimization commands")
app.add_typer(maxima_app, name="maxima", help="Maxima symbolic commands")


@app.command()
def serve():
    """Start the SageMath wrapper HTTP server."""
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)


@sat_app.command("solve")
def sat_solve(clauses: str = typer.Option(..., help="JSON list of clauses"),
              solver: str = typer.Option("picosat", help="SAT solver name")):
    print_result(solve_cnf(parse_json_arg(clauses, "clauses"), solver=solver))


@linalg_app.command("determinant")
def linalg_determinant(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.determinant(parse_json_arg(matrix, "matrix")))


@linalg_app.command("inverse")
def linalg_inverse(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.inverse(parse_json_arg(matrix, "matrix")))


@linalg_app.command("eigenvalues")
def linalg_eigenvalues(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.eigenvalues(parse_json_arg(matrix, "matrix")))


@linalg_app.command("solve")
def linalg_solve(a: str = typer.Option(..., help="JSON coefficient matrix"),
                 b: str = typer.Option(..., help="JSON right-hand side vector")):
    print_result(linalg.solve_linear_system(parse_json_arg(a, "a"), parse_json_arg(b, "b")))


@linalg_app.command("qr")
def linalg_qr(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.qr(parse_json_arg(matrix, "matrix")))


@linalg_app.command("lu")
def linalg_lu(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.lu(parse_json_arg(matrix, "matrix")))


@linalg_app.command("cholesky")
def linalg_cholesky(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.cholesky(parse_json_arg(matrix, "matrix")))


@linalg_app.command("svd")
def linalg_svd(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.svd(parse_json_arg(matrix, "matrix")))


@linalg_app.command("matrix-exp")
def linalg_matrix_exp(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.matrix_exp(parse_json_arg(matrix, "matrix")))


@linalg_app.command("right-kernel")
def linalg_right_kernel(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.right_kernel(parse_json_arg(matrix, "matrix")))


@linalg_app.command("left-kernel")
def linalg_left_kernel(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.left_kernel(parse_json_arg(matrix, "matrix")))


@linalg_app.command("charpoly")
def linalg_charpoly(matrix: str = typer.Option(..., help="JSON matrix")):
    print_result(linalg.charpoly(parse_json_arg(matrix, "matrix")))


@optimize_app.command("milp")
def optimize_milp(spec_file: str = typer.Option(..., help="JSON problem spec file")):
    try:
        with open(spec_file) as f:
            spec = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading spec file: {e}", file=sys.stderr)
        raise typer.Exit(1)
    print_result(solve_milp(
        spec["variables"], spec["objective"], spec.get("maximize", True),
        spec.get("constraints", []), var_types=spec.get("var_types"),
        solver=spec.get("solver", "GLPK"),
    ))


@optimize_app.command("find-root")
def optimize_find_root(expression: str = typer.Option(..., help="Symbolic expression"),
                       variable: str = typer.Option("x", help="Variable name"),
                       a: float = typer.Option(..., help="Interval start"),
                       b: float = typer.Option(..., help="Interval end")):
    print_result(find_root(expression, variable, a, b))


@optimize_app.command("minimize")
def optimize_minimize(expression: str = typer.Option(..., help="Symbolic expression"),
                      variables: str = typer.Option(..., help="JSON list of variable names"),
                      x0: str = typer.Option(..., help="JSON list of initial values")):
    print_result(minimize(expression, parse_json_arg(variables, "variables"), parse_json_arg(x0, "x0")))


@maxima_app.command("eval")
def maxima_eval(expression: str = typer.Option(..., help="Symbolic expression"),
                operation: str = typer.Option(..., help="Operation: simplify, differentiate, integrate"),
                variable: str = typer.Option("x", help="Variable name"),
                bounds: str = typer.Option(None, help="Integration bounds as JSON [a, b]")):
    b = parse_json_arg(bounds, "bounds") if bounds else None
    print_result(evaluate(expression, operation, variable=variable, bounds=b))


if __name__ == "__main__":
    app()