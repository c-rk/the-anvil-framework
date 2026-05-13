# System

`System` is Anvil's solvable engineering problem: a named workspace of `Quantity` values wired to `Relation` computations. It contains the five solvers, parametric sweep, sensitivity analysis, and composition API.

```python
import anvil
sys = anvil.system("my_problem")
```

---

## Building a System

### `.add()` — declare inputs

```python
# Classic style: name, value, unit
sys.add("P0",    6.9e6,  "Pa")
sys.add("T0",    3500,   "K")
sys.add("gamma", 1.25)           # dimensionless
sys.add("T0",    Q(3500, "K"))   # Quantity object

# kwargs style (unit inferred from Q)
sys.add(T0=3500*K, P0=6.9*MPa, gamma=1.25)

# With metadata
sys.add("T0", 3500, "K",
        desc="Chamber stagnation temperature",
        bounds=(200, 5000))

# Chain-able
sys.add("M", 2.0).add("gamma", 1.4)
```

**What `.add()` does internally:**
- Creates a `Quantity` and stores it in `_quantities[name]`
- Converts value to SI and records the unit hint for display
- Sets `_validated = False` (forces re-validation before next solve)

### `.set()` — override values

```python
sys.set(P0=8e6)              # bare number: keeps existing unit (Pa)
sys.set(P0=Q(1000, "psi"))   # Q object: overrides value AND unit/dim
sys.set(P0=8e6, T0=3200, gamma=1.3)  # multiple at once
```

**Difference from `.add()`:**
- `.add()` creates a new quantity (or replaces if name exists)
- `.set()` fails if name not already in system (use `.add()` first)
- `.set(P0=8e6)` with a bare number keeps the original unit hint (Pa), only changes the SI value

```python
sys.add("T", 300, "K")
sys.set(T=400)     # OK — 400 K
sys.set(T=Q(200, "R"))  # OK — 111.11 K internally, displays as 200 R

sys.set(new_var=5)  # KeyError: 'new_var' not in system
```

### `.use()` — add computation

```python
sys.use(my_function)              # plain function
sys.use(my_relation)             # Relation object
sys.use(other_system)            # System — inherits its defaults, wraps as Relation
sys.use("isentropic_ratios")     # registry name (string lookup)
sys.use(my_adapter)              # Adapter object

# With name mapping
sys.use("isentropic_ratios", map={"M": "M_exit"})
# map = {relation_param_name: workspace_variable_name}
```

When passing a **System** to `.use()`:
1. All its `_quantities` not already in the host system are inherited as defaults
2. It's wrapped via `.as_relation()` into a single callable Relation

### `.copy()` — safe duplication

```python
nozzle_a = anvil.S.rocket_nozzle.copy()
nozzle_b = anvil.S.rocket_nozzle.copy()
nozzle_a.set(P0=10e6)    # does not affect nozzle_b
```

Deep-copies all quantities and relations. Shared relation function objects are referenced, not copied — pure functions are safe. Stateful relations (adapters with side effects) are not.

### `.validate()` — pre-solve check

```python
warnings = sys.validate()   # raises ValidationError on errors; returns warning list
```

Validates:
1. No NaN/Inf in any declared quantity
2. No two relations produce the same output (conflict)
3. Every relation's required inputs are either declared or produced by another relation
4. Quantity bounds are satisfied (warning only, not error)

After validation, calls `_build_exec_order()` to determine topological order.

```python
# Example: missing input
sys = anvil.system("bad")
sys.add("M", 2.0)
sys.use("isentropic_ratios")  # needs M and gamma
try:
    sys.validate()
except ValidationError as e:
    print(e)
# ValidationError: Validation failed:
#   * 'isentropic_ratios' needs 'gamma' -- not provided.
```

Note: `gamma` has `default=1.4` in the seed RSQ — so it actually WON'T raise here. Only truly un-defaulted inputs trigger this error.

---

## Topology Detection

After `validate()`, `_build_exec_order()` runs Kahn's topological sort:

1. Builds `out_map[var] = relation_index` — which relation produces each variable
2. For each relation `i`, computes `deps[i]` = set of relations whose outputs are inputs to `i`
3. BFS: processes zero-in-degree nodes first, building `order`
4. If `len(order) == n` → acyclic → `_has_cycles = False`; `solve()` auto-selects `forward`
5. If `len(order) != n` → cycles → `_has_cycles = True`; `solve()` auto-selects `gauss_seidel`

The `_exec_order` list is used by `_forward()` to call relations in dependency order.

---

## Solvers

### `.solve_forward()` — acyclic systems

Single pass through relations in topological order. Each relation called exactly once. No convergence needed.

```python
result = sys.solve_forward()
```

**When to use:** Any system where outputs flow in one direction — no feedback loops. Fastest possible solve.

**Output:** `Result` object containing all workspace variables as Quantities.

### `.solve_gauss_seidel()` — fixed-point iteration

For systems with cycles (coupled variables). Repeatedly runs `_forward()` until convergence.

```python
result = sys.solve_gauss_seidel(
    relaxation=0.8,     # under-relaxation: 0 < ω ≤ 1. Lower = more stable, slower.
    max_iter=200,       # iteration limit
    rtol=1e-6,          # relative tolerance on max workspace change
    monitor=True,       # print live residuals per iteration
    verbose=False,      # brief residual print (less output than monitor)
)
```

**Convergence criterion:** `max_change = max over all vars: |v_new - v_prev| / |v_prev|`

Stop when `max_change < rtol`.

**Example output with `monitor=True`:**
```
  iter    0  |  residual = 2.0000e+00  |  t = 0.000s
  iter    1  |  residual = 2.3426e-01  |  t = 0.001s
  ...
  iter   32  |  residual = 6.9048e-11  |  t = 0.005s
  converged in 33 iterations
```

**Failure:** Raises `RuntimeError: Not converged after N iters (residual: X.XXe+YY)`.

**Relaxation guide:**
| System | Recommended ω |
|--------|--------------|
| Weakly coupled | 1.0 (no relaxation) |
| Moderately coupled | 0.7–0.9 |
| Strongly coupled | 0.3–0.6 |
| Strongly nonlinear | Try Newton instead |

### `.solve_newton()` — Newton-Raphson

For strongly nonlinear coupled systems. Identifies `coupled = all_outputs ∩ all_inputs`, sets them up as a nonlinear system `F(x) = 0` (residual = new value minus previous), and solves with SciPy's Powell hybrid method.

```python
result = sys.solve_newton(
    max_iter=50,
    rtol=1e-10,
    verbose=True,
)
```

**When to use:**
- Gauss-Seidel oscillates or diverges
- Strongly nonlinear relationships between coupled variables
- Need quadratic convergence

**Note:** Each Newton iteration calls `_forward()` once per coupled variable (finite-difference Jacobian). For N coupled variables this is O(N) forward passes per iteration.

**Failure:** Raises `RuntimeError` from `solve_nonlinear`.

### `.solve()` — auto-select

```python
result = sys.solve()                   # auto: forward or gauss_seidel
result = sys.solve(method="gauss_seidel", relaxation=0.7)
result = sys.solve(method="newton")
result = sys.solve(method="forward")
```

Auto-selection: `"forward"` if acyclic, `"gauss_seidel"` if cycles detected.

### History access

After `monitor=True` solve:

```python
hist = sys.history()
# [{"iteration": 0, "residual": 0.5, "wallclock": 0.001, "variables": {...}}, ...]

for h in hist:
    print(h["iteration"], h["residual"], h["wallclock"])
```

---

## Result Object

```python
result = sys.solve_forward()

result["thrust"]              # Quantity(32143.09, "N")
result["thrust"].value        # 32143.09  (display value)
result["thrust"].si           # 32143.09  (SI float)
result["thrust"].to("kN")     # Quantity(32.143, "kN")
result["thrust"].to("lbf").value  # 7224.1

result.summary()              # formatted table
result.summary(keys=["thrust", "Isp"])  # subset

result.keys()                 # all variable names
result.to_dict()              # {name: display_value}
result.to_dict(si=True)       # {name: SI_float}
result.to_csv("out.csv")      # variable,value,unit per row
result.to_json("out.json")    # {name: {value, unit}}
```

**Jupyter display:** In a Jupyter cell, `result` renders as a styled HTML table with inputs and outputs separated.

---

## `.as_relation()` — Composition

Wraps a solved System as a Relation for use inside larger Systems.

```python
nozzle_rel = nozzle.as_relation(
    inputs=["P0", "T0", "gamma", "R_gas", "A_throat", "A_exit", "P_amb"],
    outputs=["thrust", "Isp", "mdot"],
)

rocket_stage = anvil.system("full_rocket")
rocket_stage.add("P0", 10e6, "Pa")
rocket_stage.add("T0", 3500, "K")
# ... other inputs ...
rocket_stage.use(nozzle_rel)
rocket_stage.use(tsiolkovsky_rel)  # uses mdot from nozzle
result = rocket_stage.solve_forward()
```

If `inputs` or `outputs` are omitted:
- `inputs` defaults to all `_quantities` keys
- `outputs` defaults to all relation outputs NOT in `_quantities`

---

## `.optimize()` — Design Optimization

Vary design variables to minimize (or maximize) a system output, running `solve()` inside the optimizer loop.

```python
opt = sys.optimize(
    objective,          # str — output quantity name to optimize
    design_vars,        # dict — {var_name: (lo, hi)}
    minimize=True,      # False = maximize
    method="differential_evolution",
    seed=None,          # int — random seed for reproducibility
    tol=1e-6,
    maxiter=1000,
    verbose=False,      # print progress every 25 evals
    **solver_kwargs,    # passed to System.solve() for every evaluation
)
```

**`design_vars`** bounds are in the **declared display unit** of each variable (same convention as `sweep()`). The variable must already exist in the system via `.add()`.

**`**solver_kwargs`** are forwarded to every `solve()` call — use this for `method="gauss_seidel"`, `relaxation=0.7`, `max_iter=200` etc. on coupled systems.

**Global methods** (no gradient, find global optimum):
- `"differential_evolution"` (default) — robust, 10–20 variables
- `"dual_annealing"` — fewer evaluations, good for noisy objectives
- `"shgo"` — for tightly bounded or constrained problems
- `"basinhopping"` — smooth, multi-modal landscapes

**Gradient methods** (faster, smooth objectives only):
- `"L-BFGS-B"`, `"SLSQP"`, `"Nelder-Mead"`

**Solve failures:** If `solve()` raises inside the optimizer loop, that evaluation returns a large penalty value (`1e30`) rather than crashing the optimization. Passes with `verbose=True` print the failure. If all evaluations fail, `opt.success` is still `True` (from the optimizer's perspective) but `opt._result` will be `None`.

### Returns: `OptimizeResult`

```python
opt.x           # dict: {var_name: optimal_value_in_display_units}
opt.fun         # objective value at optimum
opt.success     # bool
opt.message     # str — optimizer message
opt.nit         # optimizer iterations
opt.nfev        # total System.solve() calls performed

opt["thrust"]   # Quantity at optimum — same as result["thrust"]
"Isp" in opt    # bool — check if key exists in optimum result

opt.summary()   # print design vars + full result table
```

**Jupyter display:** `opt` renders as an HTML table showing status, objective, and design variables.

### Examples

```python
import numpy as np
import anvil

# --- Maximize nozzle thrust ---
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=8e6, T0=3200, gamma=1.25, R_gas=400, P_amb=101325)

opt = nozzle.optimize(
    objective="thrust",
    design_vars={
        "A_throat": (0.002, 0.030),   # bounds in m² (declared unit)
        "A_exit":   (0.010, 0.300),
    },
    minimize=False,
    method="differential_evolution",
    seed=42,
    maxiter=400,
    verbose=True,
)

opt.summary()
print(f"Thrust: {opt.fun/1000:.2f} kN")
print(f"A_throat: {opt.x['A_throat']*1e4:.1f} cm²")
print(f"Isp: {float(opt['Isp'].value):.1f} s")   # subscript access

# --- Gradient method for smooth landscapes ---
opt_fast = nozzle.optimize(
    objective="Isp",
    design_vars={"A_throat": (0.005, 0.020), "A_exit": (0.05, 0.25)},
    minimize=False,
    method="L-BFGS-B",
    maxiter=200,
)

# --- Coupled system: pass solver_kwargs ---
hx = anvil.system("heat_exchanger")
# ... setup ...
opt_hx = hx.optimize(
    objective="Q_duty",
    design_vars={"mdot_h": (0.1, 2.0), "mdot_c": (0.1, 2.0)},
    minimize=False,
    method="differential_evolution",
    # These go to System.solve():
    method_solve="gauss_seidel",   # ← note: solver_kwargs cannot reuse 'method'
    relaxation=0.7,
    max_iter=200,
)
```

> **`method` collision:** `System.optimize()` takes its own `method` for the optimizer. To control the inner `solve()` method, wrap it: pass `solve_method="gauss_seidel"` and do `sys.solve(method=solver_kwargs.pop("solve_method", None), **solver_kwargs)`. Or subclass with a custom `solve_for_opt()` method.

### Performance

| Situation | Typical evals |
|-----------|--------------|
| 2 design vars, DE | 500–2000 |
| 4 design vars, DE | 2000–8000 |
| Any n vars, L-BFGS-B (smooth) | 50–500 |
| Noisy objective | Prefer DA or increase DE population |

Each eval is one `System.solve()` call. For coupled systems (Gauss-Seidel), this is `O(max_iter × n_relations)` function evaluations per optimizer step.

---

## `.info()` — Print Summary

```python
print(sys.info())
# System: my_nozzle
#   Inputs:
#     P0                    6.9e+06 Pa
#     T0                    3500 K
#   Relations:
#     nozzle_area_ratio
#     area_mach_supersonic
#     ...
```

---

## `__repr__()`

```python
repr(sys)
# System('rocket_nozzle', 7 vars, 8 relations)
```

---

## `anvil.solve()` — one-shot solve

Creates a temporary System with no name, adds all kwargs as inputs:

```python
result = anvil.solve(isentropic, M=2.0, gamma=1.4)
result["T0_T"]   # 1.8

result = anvil.solve("normal_shock", M1=2.5)
result["M2"]     # ~0.513
```

---

## Validation Errors

| Error | Cause |
|-------|-------|
| `ValidationError: X needs Y -- not provided` | Relation requires input Y, not declared and no default |
| `ValidationError: X produced by both A and B` | Two relations write the same output name |
| `ValidationError: X is NaN or Inf` | NaN/Inf in declared quantity |
| `RuntimeError: Not converged after N iters` | Gauss-Seidel / Newton hit iteration limit |

---

## DOF (Degrees of Freedom) Warnings

`validate()` does not verify that the system is square (equal equations and unknowns), but it emits two targeted warnings to catch the most common mistakes:

**Warning 1 — declared variable overwritten by relation:**
```python
sys.add("T0_T", 999.0)       # declared as input
sys.use("isentropic_ratios")  # also produces T0_T

sys.validate()
# WARNING: variable(s) declared via .add() are also produced by a relation —
#   declared value will be overwritten after solve: ['T0_T']
#   (This is intentional for iterative initial guesses; for forward
#   systems it may indicate a naming mismatch.)
```
This is intentional for Gauss-Seidel initial guesses. For forward-pass systems it usually indicates a naming bug.

**Warning 2 — declared variable never used:**
```python
sys.add("extra_var", 42.0)  # not an input to any relation

sys.validate()
# WARNING: variable(s) declared via .add() are not used by any relation: ['extra_var']
#   (Possible typo or unused parameter.)
```

**Suppression:** Both warnings fire only once per system instance — not on every sweep iteration or repeated solve. A fresh `anvil.system()` or `sys.copy()` resets the flag.

**What is still NOT checked:** Whether the number of relation outputs equals the number of coupled unknowns. An underdetermined system (e.g. 3 unknowns, 2 equations where nothing downstream needs the 3rd) silently produces incomplete results with no error.

---

## Performance Notes

- `solve_forward()` on a 10-relation acyclic system: <1 ms
- `solve_gauss_seidel()` converging in 33 iterations (heat exchanger): ~5 ms
- `solve_newton()` convergence in ~5 iterations for moderate systems: ~3 ms
- `sweep()` with 50 points, single-thread: ~linear in n_points × solve_time
- `sweep(parallel=4)` uses `ThreadPoolExecutor` — GIL-releasing NumPy/SciPy is faster; pure Python gains limited by GIL

The `_qty_compatible` cache on each Relation skips the try/except overhead after the first call. For iterative solvers calling relations hundreds of times, this matters.
