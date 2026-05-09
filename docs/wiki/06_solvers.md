# Solvers

All solvers are in `anvil.solvers` (or `from anvil import solvers`). They are thin, opinionated wrappers around SciPy with sensible defaults and progress output.

```python
from anvil import solvers
# or
import anvil
anvil.solvers.find_root(...)
```

---

## `find_root` — Scalar Root Finding

Find `x` such that `f(x) = 0`.

```python
x = solvers.find_root(func, x0=None, bracket=None, method="auto", tol=1e-12, maxiter=100)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func` | callable | required | `f(x) → float` |
| `x0` | float | None | Initial guess (Newton/secant) |
| `bracket` | `(a, b)` | None | Interval containing root (Brent) |
| `method` | str | `"auto"` | `"brent"`, `"newton"`, `"secant"` |
| `tol` | float | 1e-12 | Tolerance |
| `maxiter` | int | 100 | Iteration limit |

**Method selection:**
- `"auto"` + bracket → `"brent"`
- `"auto"` + x0 → `"newton"`
- Neither → `ValueError: Provide bracket=(a,b) or x0=guess.`

**SciPy backend:** `brentq` (brent), `newton` (newton/secant)

### Examples

```python
import numpy as np

# Brent's method — needs sign change in bracket
f = lambda x: x**3 - 2*x - 5
root = solvers.find_root(f, bracket=(2.0, 3.0))
# root = 2.0945514815  (exact to 1e-12)

# Newton's method — needs initial guess
root = solvers.find_root(f, x0=2.5, method="newton")
# root = 2.0945514815

# Used in built-in RSQs (e.g., area_mach_supersonic)
def residual(M, area_ratio=8.0, gamma=1.4):
    t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)
    return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio
M = solvers.find_root(residual, bracket=(1.001, 30.0))
# M = 3.9155...
```

### Performance

```
1000 calls (brent, 1e-12 tol): ~10 ms total (~10 µs/call)
```

### Limits and Errors

| Situation | Result |
|-----------|--------|
| No sign change in bracket | `ValueError: f(a) and f(b) must have different signs` |
| Function has no root in bracket | Same ValueError |
| Newton doesn't converge | `RuntimeError` (from scipy) |
| No bracket and no x0 | `ValueError: Provide bracket=(a,b) or x0=guess.` |
| Function with singularity in bracket | Brent may return NaN or incorrect result |

---

## `solve_nonlinear` — System of Nonlinear Equations

Find `x` such that `F(x) = 0` for vector-valued `F`.

```python
x = solvers.solve_nonlinear(func, x0, method="hybr", tol=1e-10, maxiter=200, jac=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func` | callable | required | `F(x) → array` same length as x |
| `x0` | array-like | required | Initial guess |
| `method` | str | `"hybr"` | SciPy root method |
| `tol` | float | 1e-10 | Tolerance |
| `maxiter` | int | 200 | Iteration limit |
| `jac` | callable | None | Jacobian df/dx; estimated by FD if None |

**Methods:**

| Method | Best for |
|--------|---------|
| `"hybr"` | General nonlinear systems (Powell hybrid) — default |
| `"lm"` | Overdetermined or ill-conditioned systems (Levenberg-Marquardt) |
| `"broyden1"` | Large sparse systems (quasi-Newton) |

**SciPy backend:** `scipy.optimize.root`

**Returns:** `ndarray` of solution `x`. Raises `RuntimeError` if not converged.

### Example

```python
import numpy as np

# Intersection of circle and line
def F(x):
    return [x[0]**2 + x[1]**2 - 1,   # x² + y² = 1
            x[0] - x[1]]               # x = y

x_sol = solvers.solve_nonlinear(F, [0.5, 0.5])
# x_sol = [0.70710678, 0.70710678]  (1/√2, 1/√2)
```

---

## `solve_ode` — Explicit ODE (non-stiff)

Integrate `dy/dt = f(t, y)` using explicit Runge-Kutta methods.

```python
r = solvers.solve_ode(func, t_span, y0,
    method="RK45",
    t_eval=None,
    rtol=1e-8,
    atol=1e-10,
    max_step=np.inf,
    events=None,
    verbose=False)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `func` | required | `f(t, y) → dy/dt` array |
| `t_span` | required | `(t0, tf)` integration interval |
| `y0` | required | Initial conditions, length n |
| `method` | `"RK45"` | Integration method (see table) |
| `t_eval` | None | Times to store output; None → adaptive |
| `rtol` | 1e-8 | Relative tolerance |
| `atol` | 1e-10 | Absolute tolerance |
| `max_step` | `np.inf` | Maximum step size |
| `events` | None | Event functions; zeros trigger stop |
| `verbose` | False | Print progress every 10% of interval |

**Methods:**

| Method | Order | Best for |
|--------|-------|---------|
| `"RK45"` | 4/5 | General non-stiff (default) |
| `"RK23"` | 2/3 | Low accuracy or fast solutions needed |
| `"DOP853"` | 8/5/3 | High accuracy, smooth problems |

**Returns dict:**

| Key | Description |
|-----|-------------|
| `"t"` | Time array, shape (n_steps,) |
| `"y"` | Solution, shape (n_states, n_steps) |
| `"success"` | bool — converged? |
| `"message"` | str — solver message |
| `"nfev"` | int — function evaluations |
| `"sol"` | Dense output callable: `sol.sol(t) → y(t)` |

> **Note:** `"sol"` key contains the full SciPy OdeResult object. Call `r["sol"].sol(t_array)` for dense interpolation.

### Examples

```python
import numpy as np

# Harmonic oscillator: y'' = -y
def harmonic(t, y):
    return [y[1], -y[0]]

t_eval = np.linspace(0, 2*np.pi, 100)
r = solvers.solve_ode(harmonic, (0, 2*np.pi), [0.0, 1.0], t_eval=t_eval)
# r["y"][0, -1] ≈ 0.0  (y(2π) = sin(2π) = 0)
# r["nfev"] = 506

# Event-driven: stop when y[0] = 0.5
def hit_half(t, y): return y[0] - 0.5
hit_half.terminal = True
r = solvers.solve_ode(harmonic, (0, 10), [0.0, 1.0], events=hit_half)
```

### Failure / success flag

**Important:** `r["success"]` may be `True` even when the solution is numerically garbage. Example: a function with a singularity may appear to succeed but produce nonsensical values:

```python
# f blows up but ODE "succeeds"
r = solvers.solve_ode(lambda t, y: [1.0/(y[0]-0.5)], (0, 0.4), [0.0])
print(r["success"])   # True — SciPy says OK
```

Always sanity-check the output.

---

## `solve_ode_stiff` — Implicit ODE (stiff)

```python
r = solvers.solve_ode_stiff(func, t_span, y0,
    method="BDF",
    t_eval=None,
    rtol=1e-6,
    atol=1e-10,
    jac=None,
    events=None,
    verbose=False)
```

Same interface as `solve_ode` with two additional parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `method` | `"BDF"` | `"BDF"` or `"Radau"` |
| `jac` | None | Jacobian `df/dy`; estimated by FD if None |

**Methods:**

| Method | Best for |
|--------|---------|
| `"BDF"` | Large stiff systems, combustion kinetics (default) |
| `"Radau"` | Small stiff systems, higher accuracy |

**Stiff systems:** ODEs with widely separated time scales. Combustion (fast chemistry + slow heat release), electrical circuits, diffusion-reaction equations.

**Failure:** Raises `RuntimeError` with diagnostic message if not `verbose`:
```
RuntimeError: Stiff ODE solver (BDF) failed: [message]
  Try: looser tolerances (rtol=1e-4), different method, or provide a Jacobian via jac=.
```

With `verbose=True`: prints progress, returns result even on failure.

### Example

```python
# Stiff exponential decay with forcing
def stiff_decay(t, y):
    return [-1000*y[0] + 3000 - 2000*np.exp(-t),
            -1000*(y[0] - np.exp(-t))]

r = solvers.solve_ode_stiff(stiff_decay, (0, 0.05), [0.0, 0.0], rtol=1e-4)
print(r["success"])   # True
print(r["nfev"])      # much fewer evals than RK45 would need
```

---

## `solve_bvp` — Boundary Value Problem

Solve `dy/dx = f(x, y)` with `bc(y(a), y(b)) = 0`.

```python
r = solvers.solve_bvp(func, bc, x, y_init,
    tol=1e-3,
    max_nodes=1000,
    verbose=False)
```

| Parameter | Description |
|-----------|-------------|
| `func` | `f(x, y) → dy/dx`, shape `(n,)` or `(n, m)` |
| `bc` | `bc(ya, yb) → residual`, length n |
| `x` | Initial mesh, 1D array from a to b |
| `y_init` | Initial guess, shape `(n, len(x))` |
| `tol` | Residual tolerance (default 1e-3) |
| `max_nodes` | Maximum mesh refinement nodes |
| `verbose` | Detailed solver output |

**Returns dict:**

| Key | Description |
|-----|-------------|
| `"x"` | Final mesh, shape (m,) |
| `"y"` | Solution at mesh, shape (n, m) |
| `"success"` | bool |
| `"message"` | str |
| `"residual"` | RMS residuals array |
| `"sol"` | Dense callable: `sol(x) → y(x)` |

**SciPy backend:** `scipy.integrate.solve_bvp`

**Failure:** Raises `RuntimeError` if not verbose.

### Example: y'' = -y, y(0) = 0, y(π) = 0

```python
import numpy as np

def f(x, y):
    return np.vstack([y[1], -y[0]])    # [y', y''] = [y[1], -y[0]]

def bc(ya, yb):
    return np.array([ya[0], yb[0]])    # y(0)=0, y(π)=0

x_init = np.linspace(0, np.pi, 5)
y_init = np.zeros((2, 5))
y_init[0] = np.sin(x_init)            # initial guess: sin(x)

r = solvers.solve_bvp(f, bc, x_init, y_init)

x_fine = np.linspace(0, np.pi, 100)
y_fine = r["sol"](x_fine)[0]
# y_fine[50] ≈ 1.0  (sin(π/2) = 1)
```

### Accuracy

With default `tol=1e-3`:
```
y(π/2) = 1.000000  (exact: 1.0)
```

BVP mesh adapts automatically — more nodes where curvature is high. `max_nodes=1000` caps mesh refinement.

---

## `solve_pde_heat_1d` — 1D Parabolic PDE

Solve `∂u/∂t = α · ∂²u/∂x² + f(x, t, u)` using the Crank-Nicolson scheme.

```python
r = solvers.solve_pde_heat_1d(
    alpha,           # diffusivity [m²/s]
    x_span,          # (x_left, x_right)
    t_span,          # (t_start, t_end)
    u_init,          # callable u(x) or array of length nx
    bc_left=None,    # Dirichlet left: float or callable(t); None = zero-flux Neumann
    bc_right=None,   # Dirichlet right: float or callable(t); None = zero-flux Neumann
    source=None,     # source term f(x, t, u) → array; None = no source
    nx=100,          # spatial grid points
    nt=None,         # time steps; auto if None (CFL-like estimate)
    verbose=False,
)
```

**Returns dict:**

| Key | Shape | Description |
|-----|-------|-------------|
| `"x"` | `(nx,)` | Spatial grid |
| `"t"` | `(nt+1,)` | Time array |
| `"u"` | `(nt+1, nx)` | Solution at all times |
| `"dx"` | float | Grid spacing |
| `"dt"` | float | Time step used |

### Crank-Nicolson scheme

Unconditionally stable, 2nd-order accurate in both space and time. The tridiagonal system is solved at each time step using `scipy.linalg.solve_banded`.

**Automatic `nt` selection:** `dt ≈ min(0.25 × dx²/α, (tf-t0)/100)`. This targets temporal accuracy, not just stability.

**Boundary conditions:**
- Float or callable → Dirichlet (fixed value)
- `None` → zero-flux Neumann (`∂u/∂x = 0` at boundary via ghost point)
- Callable signature: `bc_left(t) → float`

**Source term:** `source(x, t, u) → ndarray` of length nx. Half-step approximation: `0.5*dt*(f_n + f_{n+1})`.

### Examples

```python
import numpy as np

# Heat pulse diffusing with Dirichlet = 0 at both ends
r = solvers.solve_pde_heat_1d(
    alpha=1e-5,
    x_span=(0, 1),
    t_span=(0, 10),
    u_init=lambda x: np.exp(-100*(x-0.5)**2),
    bc_left=0.0,
    bc_right=0.0,
    nx=100,
)
# r["u"][-1]  — final temperature profile at t=10s
# r["u"][0]   — initial profile

# Accuracy check: sin(πx) initial condition decays as exp(-π²αt)sin(πx)
r2 = solvers.solve_pde_heat_1d(
    alpha=1e-4,
    x_span=(0, 1), t_span=(0, 1),
    u_init=lambda x: np.sin(np.pi*x),
    bc_left=0.0, bc_right=0.0, nx=50,
)
numerical  = r2["u"][-1].max()     # 0.998501
analytical = np.exp(-np.pi**2*1e-4)  # 0.999014
# Relative error: 5.13e-4 (0.05%)

# Time-varying boundary condition
r3 = solvers.solve_pde_heat_1d(
    alpha=1e-5,
    x_span=(0, 1), t_span=(0, 100),
    u_init=lambda x: np.zeros_like(x),
    bc_left=lambda t: 100.0 * np.sin(0.1*t),  # oscillating left BC
    bc_right=0.0,
    nx=50,
)
```

### Limits

| Limit | Value/Notes |
|-------|-------------|
| Spatial accuracy | 2nd order in dx |
| Temporal accuracy | 2nd order in dt (Crank-Nicolson) |
| Stability | Unconditionally stable (any dt) |
| Source accuracy | Half-step (1st order in source nonlinearity) |
| Dimensions | 1D only |
| Geometry | Uniform Cartesian grid only |
| BC types | Dirichlet or zero-flux Neumann only |
| Nonlinear diffusion | Not supported (α must be constant) |

---

## `minimize` — Scalar Optimization

Minimize `f(x)` where `x` is a vector.

```python
r = solvers.minimize(func, x0,
    method="L-BFGS-B",
    bounds=None,
    tol=1e-8,
    maxiter=500,
    jac=None)
```

**Returns dict:**

| Key | Description |
|-----|-------------|
| `"x"` | Optimal solution |
| `"fun"` | Objective value at optimum |
| `"success"` | bool |
| `"message"` | str |
| `"nit"` | Iterations |

**Methods:**

| Method | Supports bounds | Gradient | Best for |
|--------|----------------|----------|---------|
| `"L-BFGS-B"` | Yes | Numerical or analytical | General, large-scale (default) |
| `"SLSQP"` | Yes | Numerical | Equality + inequality constraints |
| `"Nelder-Mead"` | No | None | Gradient-free, noisy functions |
| `"COBYLA"` | No | None | Constrained, no gradient |

**Bounds:** List of `(lo, hi)` per dimension. `None` in a tuple = unbounded:
```python
bounds=[(0, None), (0, 10), (None, None)]  # x[0]≥0, 0≤x[1]≤10, x[2] unbounded
```

### Examples

```python
# Simple quadratic
r = solvers.minimize(lambda x: (x[0]-1)**2 + (x[1]-2)**2, [0.0, 0.0])
# r["x"] = [1.0, 2.0]  r["fun"] = 5e-17

# Rosenbrock — classic test
from scipy.optimize import rosen
r = solvers.minimize(rosen, [0.0, 0.0], method="L-BFGS-B")
# r["x"] ≈ [1.0, 1.0]   r["fun"] ≈ 0

# With bounds and analytical Jacobian
def f_and_grad(x):
    val = x[0]**2 + x[1]**2
    grad = [2*x[0], 2*x[1]]
    return val, grad
r = solvers.minimize(
    lambda x: f_and_grad(x)[0], [5.0, 5.0],
    bounds=[(1, None), (1, None)],
    jac=lambda x: f_and_grad(x)[1],
)
# r["x"] = [1.0, 1.0]  (constrained minimum)
```

---

## Summary Table

| Solver | Problem type | SciPy backend | Key params |
|--------|-------------|--------------|-----------|
| `find_root` | `f(x)=0`, scalar | `brentq`, `newton` | `bracket`, `x0`, `method` |
| `solve_nonlinear` | `F(x)=0`, vector | `root` | `method`, `jac` |
| `solve_ode` | `dy/dt=f`, non-stiff | `solve_ivp` | `method`, `t_eval`, `rtol/atol` |
| `solve_ode_stiff` | `dy/dt=f`, stiff | `solve_ivp` | `method`, `jac` |
| `solve_bvp` | BVP | `solve_bvp` | `tol`, `max_nodes` |
| `solve_pde_heat_1d` | 1D parabolic PDE | tridiagonal (scipy) | `alpha`, `nx`, `bc_*` |
| `minimize` | `min f(x)` | `minimize` | `method`, `bounds`, `jac` |

---

## Accuracy Benchmarks

| Test | Numerical | Analytical | Relative error |
|------|-----------|-----------|---------------|
| `find_root` (brent, tol=1e-12) | 2.09455148154 | 2.09455148154 | <1e-13 |
| `solve_ode` harmonic y(2π) | 0.00000000 | 0.0 | ~1e-12 |
| `solve_pde_heat_1d` sin decay | 0.998501 | 0.999014 | 5e-4 |
| `solve_nonlinear` circle | [0.7071068, 0.7071068] | [1/√2, 1/√2] | <1e-10 |
