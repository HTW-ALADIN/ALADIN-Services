"""SAT solving via SageMath's SAT solvers — pure functions, no sandbox.

Each function performs SageMath work directly. The dispatcher is responsible
for running these in a subprocess with the configured timeout and limits.
"""


def solve_cnf(clauses, solver="picosat"):
    """Solve a CNF formula using a SageMath SAT solver."""
    solver = solver.lower()
    if solver not in ("picosat", "cryptominisat", "glucose"):
        raise ValueError(
            f"unsupported solver '{solver}'. "
            "supported: picosat, cryptominisat, glucose"
        )
    for clause in clauses:
        for lit in clause:
            if lit == 0:
                raise ValueError("variable index 0 is forbidden in DIMACS format")

    from sage.sat.solvers.dimacs import CryptoMiniSat, GlucoseSyrup, PicoSAT

    s = {"picosat": PicoSAT, "cryptominisat": CryptoMiniSat, "glucose": GlucoseSyrup}[solver]()
    for clause in clauses:
        s.add_clause(tuple(clause))
    sol = s()
    if sol is False:
        return {"satisfiable": False, "assignment": None, "solver": solver}
    return {
        "satisfiable": True,
        "assignment": {str(i): bool(sol[i]) for i in range(1, len(sol))},
        "solver": solver,
    }