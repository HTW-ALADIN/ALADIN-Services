# SageMath Wrapper Service

## Purpose

HTTP/CLI wrapper around SageMath for symbolic computation (SAT solving, linear
algebra, mixed-integer linear programming, Maxima integration). All SageMath
calls run inside a sandboxed subprocess with resource limits and timeout.

## Architecture

```
Client ──► HTTP (FastAPI) ──► core/*.py ──► run_sandboxed() ──► SageMath
Client ──► CLI  (Typer)   ──► core/*.py ──► run_sandboxed() ──► SageMath
```

All four modules (`sat.py`, `linalg.py`, `optimize.py`, `maxima.py`) exclusively
call `src.sandbox.executor.run_sandboxed()` to execute SageMath code in an
isolated child process using `os.fork()`, `resource.setrlimit(RLIMIT_AS)`,
and timeout (`SIGKILL`).

## Implemented SageMath Functionality

The following SageMath APIs are currently exposed through the HTTP/CLI interface:

| Area | SageMath classes / methods used | Endpoints |
|------|-------------------------------|-----------|
| **SAT solving** | `sage.sat.solvers.dimacs.{PicoSAT, CryptoMiniSat, GlucoseSyrup}` — `.add_clause()`, `solver_obj()` | 1 (`/v1/sat/solve`) |
| **Linear algebra** | `sage.all.matrix(RDF, ...)`, `vector(RDF, ...)` — `.determinant()`, `.inverse()`, `.eigenvalues()`, `.solve_right()`, `.QR()`, `.LU()`, `.cholesky()`, `.SVD()`, `.exp()`, `.right_kernel()`, `.left_kernel()`, `.charpoly()` | 13 (`determinant`, `inverse`, `eigenvalues`, `solve`, `qr`, `lu`, `cholesky`, `svd`, `matrix-exp`, `right-kernel`, `left-kernel`, `charpoly`) |
| **Mixed-integer linear programming** | `sage.numerical.mip.MixedIntegerLinearProgram` — `.new_variable()`, `.set_objective()`, `.add_constraint()`, `.solve()`, `.get_values()`, `.set_integer()` | 1 (`/v1/optimize/milp`) |
| **Symbolic calculus** | `sage.all.SR()`, `var()` — `.simplify_full()`, `.diff()`, `.integrate()` (indefinite + definite) | 1 (`/v1/maxima/evaluate` with 3 operations) |

## Future Extensions (based on the SageMath Tutorial)

The [SageMath Tutorial](https://doc.sagemath.org/html/en/tutorial/) covers many
more areas that could be added as new endpoints:

### Number Theory (`sage.all`, `Integer`, `ZZ`)
- **Prime factorization:** `factor(n)` — decompose an integer into primes
- **GCD / LCM:** `gcd(a, b)`, `lcm(a, b)`
- **Modular arithmetic:** `mod(a, n)`, `pow(a, e, n)` (modular exponentiation)
- **Diophantine equations:** `solve_mod(eq, mod_ulus)`
- **Elliptic curves:** `EllipticCurve([a, b])` — points, addition, rank

### Polynomials (`sage.all.PolynomialRing`, `QQ[]`, `ZZ[]`)
- **Root finding:** `poly.roots(RR)`, `poly.roots(CC)` — real and complex roots
- **Polynomial GCD / factorization:** `poly.gcd()`, `poly.factor()`
- **Groebner bases:** `ideal(*polynomials).groebner_basis()`
- **Polynomial interpolation:** `PolynomialRing(QQ, 'x').lagrange_polynomial(points)`

### Calculus (beyond current `maxima` operations)
- **Limits:** `limit(f(x), x=a)`, `limit(f(x), x=oo)`
- **Series expansion:** `series(f(x), x, a, n)` — Taylor/Maclaurin series
- **Laplace / Fourier transforms:** `laplace(f(t), t, s)`, `fourier(f(x), x, k)`
- **Partial derivatives:** `f.diff(x, y)` — mixed partial derivatives
- **Gradient / divergence / curl:** `gradient(f)`, `divergence(v)`, `curl(v)`

### Linear Algebra (extensions)
- **Matrix exponential (higher precision):** `m.exp()` via `SR` (RDF version already implemented)
- **Polar decomposition:** `m.polar()`
- **Matrix functions:** `m.sqrt()`, `m.log()`
- **Jordan normal form:** `m.jordan_form()`

### Group Theory (`sage.groups`)
- **Permutation groups:** `PermutationGroup(...)` — group operations, cosets
- **Symmetric / alternating / dihedral groups:** `SymmetricGroup(n)`, `DihedralGroup(n)`
- **Group actions:** orbits, stabilizers, conjugacy classes

### Statistics and Probability (`sage.stats`)
- **Descriptive stats:** `mean(v)`, `median(v)`, `variance(v)`, `std(v)`
- **Distributions:** `RealDistribution('gaussian', ...)`, `BinomialDistribution(...)`
- **Hypothesis testing:** `stats.ttest(...)`, `stats.f_oneway(...)`

### 2D / 3D Plotting
- **Function plots:** `plot(f, (x, a, b))` — render and return as PNG/SVG
- **Parametric / contour / implicit plots:** `parametric_plot(...)`, `contour_plot(...)`
- **3D surfaces:** `plot3d(f, (x, a, b), (y, c, d))`

### Cryptography
- **RSA:** `RSA.gen_key(...)`, encrypt/decrypt
- **Discrete log:** `discrete_log(a, base)`
- **Diffie-Hellman:** `DiffieHellman(...)`

**Note on security:** Any future endpoint that accepts user-supplied expressions
must follow the same pattern as the Maxima module — whitelist validation before
the sandbox call, rejection of dangerous keywords, and a strict length limit.
The sandbox (`run_sandboxed()`) provides process isolation, but input validation
is the first line of defense.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Healthcheck (200 OK) |
| `/v1/sat/solve` | POST | Solve a CNF SAT formula |
| `/v1/linalg/determinant` | POST | Determinant of a square matrix |
| `/v1/linalg/inverse` | POST | Inverse of a square matrix |
| `/v1/linalg/eigenvalues` | POST | Eigenvalues of a square matrix |
| `/v1/linalg/solve` | POST | Solve linear system A·x = b |
| `/v1/linalg/qr` | POST | QR decomposition |
| `/v1/linalg/lu` | POST | LU decomposition with pivoting |
| `/v1/linalg/cholesky` | POST | Cholesky decomposition |
| `/v1/linalg/svd` | POST | Singular value decomposition |
| `/v1/linalg/matrix-exp` | POST | Matrix exponential |
| `/v1/linalg/right-kernel` | POST | Right kernel (nullspace) |
| `/v1/linalg/left-kernel` | POST | Left kernel |
| `/v1/linalg/charpoly` | POST | Characteristic polynomial |
| `/v1/optimize/milp` | POST | Solve a mixed-integer linear program |
| `/v1/maxima/evaluate` | POST | Transform a symbolic expression |

### Example: SAT solving

```sh
curl -X POST http://localhost:8000/v1/sat/solve \
  -H "Content-Type: application/json" \
  -d '{"clauses": [[1,2],[-1,2],[1,-2]], "solver": "picosat"}'
```
```json
{"satisfiable": true, "assignment": {"1": true, "2": true}, "solver": "picosat"}
```

### Example: Determinant

```sh
curl -X POST http://localhost:8000/v1/linalg/determinant \
  -H "Content-Type: application/json" \
  -d '{"matrix": [[1,2],[3,4]]}'
```
```json
{"result": -2.0, "error": null}
```

### Example: MILP (tutorial reference case)

```sh
curl -X POST http://localhost:8000/v1/optimize/milp \
  -H "Content-Type: application/json" \
  -d '{
    "variables": ["x","y"],
    "objective": {"x": 2, "y": 1},
    "maximize": true,
    "constraints": [
      {"coeffs": {"x": 3, "y": 4}, "max": 2.5},
      {"coeffs": {"x": 1.5, "y": 0.5}, "max": 4, "min": 0.5}
    ],
    "var_types": {"x": "real", "y": "real"}
  }'
```
```json
{"status": "optimal", "objective_value": 1.6666666666666667, "values": {"x": 0.8333333333333334, "y": 0.0}}
```

### Example: Maxima differentiation

```sh
curl -X POST http://localhost:8000/v1/maxima/evaluate \
  -H "Content-Type: application/json" \
  -d '{"expression": "x^3", "operation": "differentiate", "variable": "x"}'
```
```json
{"result": "3*x^2", "error": null}
```

## CLI

All API functions are also available as CLI commands — they call the core
functions directly (no HTTP call to self):

```sh
# SAT
sagemath-wrapper sat solve --clauses '[[1,2],[-1,2],[1,-2]]' --solver picosat

# Linear algebra
sagemath-wrapper linalg determinant --matrix '[[1,2],[3,4]]'
sagemath-wrapper linalg qr --matrix '[[1,2],[3,4]]'
sagemath-wrapper linalg lu --matrix '[[4,3],[6,3]]'
sagemath-wrapper linalg cholesky --matrix '[[4,2],[2,3]]'
sagemath-wrapper linalg svd --matrix '[[1,2,3],[4,5,6]]'
sagemath-wrapper linalg matrix-exp --matrix '[[1,0],[0,1]]'
sagemath-wrapper linalg right-kernel --matrix '[[1,2],[2,4]]'
sagemath-wrapper linalg left-kernel --matrix '[[1,2],[2,4]]'
sagemath-wrapper linalg charpoly --matrix '[[1,2],[3,4]]'
sagemath-wrapper linalg solve --a '[[2,1],[1,3]]' --b '[5,10]'

# Optimization (problem spec as JSON file)
sagemath-wrapper optimize milp --spec-file problem.json

# Maxima
sagemath-wrapper maxima eval --expression 'x^3' --operation differentiate --variable x

# Start the HTTP server
sagemath-wrapper serve
```

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Memory | **2 GB RAM** | 4 GB+ |
| CPU | 2 cores | 4 cores |
| GPU | — | not required |
| Image size | ~5 GB | 5–10 GB |

The large image size comes from the underlying SageMath base image, which
includes a complete mathematical environment (Maxima, GAP, PARI/GP, Singular,
etc.).

## Container

```sh
make docker-build   # build the image
make docker-run     # start the container (port 8000)
```

The container runs as a **non-root user** (`sageuser`) with a **HEALTHCHECK**
against `/healthz` (interval 15s, start period 30s).

## Security Model

### Sandbox (`run_sandboxed`)

Every `core/*` call executes in an **isolated child process**:

- **Process isolation:** `os.fork()` + `Pipe` — child has its own address space,
  no shared-state side effects between calls
- **Memory limit:** `resource.setrlimit(RLIMIT_AS, 100 MB)` in the child process
- **Timeout:** `SIGKILL` is sent on expiry (default 5s, Maxima 3s)
- **Error handling:** Exceptions in the child are transferred via Pipe to the
  parent process, never thrown uncontrollably

### Maxima Whitelist

The client must **NOT** inject raw Maxima expressions for direct evaluation.
Every expression goes through validation before any SageMath call:

1. **Length limit:** Max 500 characters (DoS prevention)
2. **Keyword blacklist:** `system`, `openr`, `openw`, `load`, `os.`, `eval`,
   `exec`, `__import__`, `subprocess`, `compile`, `execfile` are blocked
3. **Character whitelist:** Only numbers, known function names (`sin`, `cos`,
   `exp`, `log`, `sqrt`, …), variable names `[a-zA-Z_][a-zA-Z0-9_]*`, and
   operators `+-*/^()[]` are allowed — everything else is rejected

### Pre-Sandbox Validation

All `core/*.py` functions validate their inputs **before** calling
`run_sandboxed()` — e.g. DIMACS convention (index 0 forbidden), square matrices,
supported solvers, unknown variables. Errors raise `ValueError`, which becomes
HTTP 400 in the API router (no stacktrace leak, see global exception handlers
in `main.py`).

### No User Code Execution

Nowhere in the system is user-supplied Python code executed via `eval()` or
`exec()`. The client supplies only data (lists, dicts, strings) that are
translated into parameters for fixed SageMath functions.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `prep` | Install dependencies |
| `build` | *(not yet implemented)* |
| `test` | Run all tests |
| `lint` | Ruff code quality check |
| `start` | *(not yet implemented)* |
| `clean` | Remove build artifacts |
| `docker-build` | Build the Docker image |
| `docker-run` | Start the container |
| `generate-openapi` | Export OpenAPI spec as YAML |

## Local Development

```sh
make prep
make test
make lint
```