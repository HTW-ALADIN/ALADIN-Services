"""SAT solving via SageMath's SAT solvers, sandboxed via run_sandboxed."""

import src.sandbox.executor as _executor


def solve_cnf(clauses, solver="picosat"):
    """Solve a CNF formula inside the sandbox using a SageMath SAT solver."""
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

    result = _executor.run_sandboxed(
        _solve_cnf_inner, {"clauses": clauses, "solver": solver}
    )
    if not result["ok"]:
        raise RuntimeError(f"sandbox execution failed: {result['error']}")
    return result["result"]


def _solve_cnf_inner(clauses, solver):
    """Run inside sandbox child process — SageMath imports here."""
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