# SageMath Wrapper Service

HTTP and CLI access to a curated set of SageMath operations. Requests are
validated against the operation registry and executed in a separate,
resource-limited SageMath process.

## Included algorithms

The service currently exposes 24 operations. Each registry ID maps to
`POST /v1/<id-with-dots-replaced-by-slashes>`; `/docs` contains the exact
request schema.

### Linear algebra

| Registry ID | Operation | Result |
| --- | --- | --- |
| `linalg.determinant` | Determinant of a square matrix | scalar |
| `linalg.inverse` | Inverse of a square matrix | matrix |
| `linalg.eigenvalues` | Eigenvalues (exact, supports complex numbers) | vector (complex as `[real, imag]`) |
| `linalg.eigenvectors_left` | Left eigenvectors with eigenvalues & multiplicities | `[{eigenvalue, eigenvectors, multiplicity}]` |
| `linalg.eigenvectors_right` | Right eigenvectors with eigenvalues & multiplicities | `[{eigenvalue, eigenvectors, multiplicity}]` |
| `linalg.solve` | Solve `A · x = b` | vector |
| `linalg.qr` | QR decomposition | `{Q, R}` |
| `linalg.lu` | LU decomposition with pivoting | `{P, L, U}` |
| `linalg.cholesky` | Cholesky decomposition | matrix |
| `linalg.svd` | Singular value decomposition | `{U, Sigma, V}` |
| `linalg.matrix-exp` | Matrix exponential | matrix |
| `linalg.right-kernel` | Right kernel basis | matrix |
| `linalg.left-kernel` | Left kernel basis | matrix |
| `linalg.charpoly` | Characteristic polynomial | string |
| `linalg.kernel` | Kernel basis matrix | matrix |
| `linalg.echelon_form` | Row echelon form | matrix |
| `linalg.rank` | Matrix rank | scalar |
| `linalg.matrix_vector_product` | Matrix-vector product | vector |
| `linalg.vector_matrix_product` | Vector-matrix product | vector |

### Optimisation, symbolic mathematics and SAT

| Registry ID | Operation | Result |
| --- | --- | --- |
| `optimize.milp` | Mixed-integer linear program | status, objective value and variables |
| `optimize.find-root` | Root of an expression in an interval | scalar |
| `optimize.minimize` | Unconstrained minimisation | vector |
| `maxima.evaluate` | `simplify`, `differentiate`, `integrate`, `solve`, `limit`, `series` or `laplace` | operation-dependent |
| `sat.solve` | CNF SAT solving with PicoSAT, CryptoMiniSat or Glucose | satisfiability and assignment |

## Implemented SageMath Functionality

The following SageMath APIs are currently exposed through the HTTP/CLI interface:

| Area | SageMath classes / methods used | Endpoints |
|------|-------------------------------|-----------|
| **SAT solving** | `sage.sat.solvers.dimacs.{PicoSAT, CryptoMiniSat, GlucoseSyrup}` — `.add_clause()`, `solver_obj()` | 1 (`/v1/sat/solve`) |
| **Linear algebra** | `sage.all.matrix(RDF, ...)`, `Matrix(...)`, `vector(RDF, ...)`, `vector(...)` — `.determinant()`, `.inverse()`, `.eigenvalues()`, `.eigenvectors_left()`, `.eigenvectors_right()`, `.solve_right()`, `.QR()`, `.LU()`, `.cholesky()`, `.SVD()`, `.exp()`, `.right_kernel()`, `.left_kernel()`, `.charpoly()`, `.kernel()`, `.echelon_form()`, `.rank()` | 19 (`determinant`, `inverse`, `eigenvalues`, `eigenvectors_left`, `eigenvectors_right`, `solve`, `qr`, `lu`, `cholesky`, `svd`, `matrix-exp`, `right-kernel`, `left-kernel`, `charpoly`, `kernel`, `echelon_form`, `rank`, `matrix_vector_product`, `vector_matrix_product`) |
| **Mixed-integer linear programming** | `sage.numerical.mip.MixedIntegerLinearProgram` — `.new_variable()`, `.set_objective()`, `.add_constraint()`, `.solve()`, `.get_values()`, `.set_integer()` | 1 (`/v1/optimize/milp`) |
| **Symbolic calculus** | `sage.all.SR()`, `var()` — `.simplify_full()`, `.diff()`, `.integrate()` (indefinite + definite) | 1 (`/v1/maxima/evaluate` with 3 operations) |

## Use the service

### Run it

Docker is the simplest option because it includes SageMath:

```sh
make docker-build
make docker-run
```

The API is then available at `http://localhost:8000`. Check it with:

```sh
curl http://localhost:8000/healthz
```

For local development, run from this directory with a SageMath installation:

```sh
sage -python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Call an operation

Every operation has a `POST /v1/<id>` endpoint, where dots in its registry ID
become slashes. For example, `linalg.determinant` becomes
`POST /v1/linalg/determinant`.

```sh
curl -X POST http://localhost:8000/v1/linalg/determinant \
  -H 'Content-Type: application/json' \
  -d '{"matrix": [[1, 2], [3, 4]]}'
# -2.0
```

```sh
curl -X POST http://localhost:8000/v1/sat/solve \
  -H 'Content-Type: application/json' \
  -d '{"clauses": [[1, 2], [-1, 2], [1, -2]]}'
```

The authoritative API documentation is served by the running service:

```text
http://localhost:8000/docs
http://localhost:8000/openapi.json
```

Example requests for the VS Code REST Client extension live in `http-tests/`.

### CLI

The CLI reads the same registry as the API. Supply the complete input as JSON:

```sh
sage -python -m src.cli.main linalg determinant \
  --payload '{"matrix": [[1, 2], [3, 4]]}'

sage -python -m src.cli.main optimize milp --spec-file problem.json
```

Use `--help` at every level to discover registered operations:

```sh
sage -python -m src.cli.main linalg --help
sage -python -m src.cli.main linalg determinant --help
```

## Add a SageMath operation

The registry is the source of truth. Adding an entry creates the HTTP route,
CLI command and OpenAPI request schema automatically.

### 1. Prefer a registry template

Add an entry to the appropriate `registry/*.yaml` file. Templates are for
small, fixed SageMath snippets; they can use `Matrix`, `vector` and other
`sage.all` names directly.

```yaml
- id: linalg.trace
  summary: Trace of a square matrix
  kind: template
  input_schema:
    type: object
    properties:
      matrix:
        type: array
        items:
          type: array
          items:
            type: number
    required: [matrix]
  output_type: scalar
  timeout_s: 5.0
  sage_template: |
    A = Matrix({{ matrix|sage_literal }})
    __result__ = A.trace()
```

Use `|sage_literal` for every value interpolated into a template. Templates
must assign their return value to `__result__`.

### 2. Use a Python function only for non-trivial logic

Put reusable validation or multi-step SageMath work in `src/core/<area>.py`.
The function must return JSON-compatible data or raise `ValueError` for a
client error. Do not start processes or enforce timeouts in core code; the
dispatcher does that once for every operation.

```yaml
- id: number_theory.factor
  summary: Prime factorisation of an integer
  kind: function
  input_schema:
    type: object
    properties:
      n: {type: integer}
    required: [n]
  output_type: object
  timeout_s: 5.0
  function_ref: src.core.number_theory:factor
```

`output_type` is one of `scalar`, `vector`, `matrix`, `object` or
`sat_result`. Pick the narrowest correct type. Function references must use
the `src.core...` module path.

### 3. Verify the change

```sh
PYTHONPATH=. python -m pytest tests/unit tests/contract -m 'not docker' -q
python -m ruff check src tests
make generate-openapi
```

Add a focused unit test for Python logic and a contract test when the public
HTTP or CLI behaviour is new. Run the Docker smoke test in CI or a Docker-capable
environment.

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

## Project map

| Location | Responsibility |
| --- | --- |
| `registry/` | Operation definitions, input schemas and timeouts |
| `src/api/` | Dynamic FastAPI routes |
| `src/cli/main.py` | Dynamic Typer CLI |
| `src/registry/dispatcher.py` | Validation, template rendering and result checks |
| `src/sandbox/executor.py` | Isolated SageMath subprocess and resource limits |
| `src/core/` | SageMath-specific operation implementations |
| `tests/` | Unit, API/CLI contract and Docker smoke tests |

## Development commands

```sh
make prep                 # install test dependencies
make test                 # run tests
make lint                 # run Ruff
make generate-openapi     # write openapi/openapi.yaml
```

The Docker smoke test requires a Docker daemon and is skipped when unavailable.

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
