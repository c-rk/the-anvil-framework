# Limits, Gotchas, and Known Issues

Comprehensive list of what Anvil cannot do, where it behaves unexpectedly, and how to work around issues.

---

## 1. System & Solver Limitations

### DOF analysis — partial ✓ fixed

`validate()` now emits warnings for two common DOF mistakes:

1. **Declared variable also produced by relation** — silent overwrite (intentional for iterative initial guesses, but likely a naming bug in forward systems):

```python
sys.add("T0_T", 999.0)       # declared
sys.use("isentropic_ratios")  # also produces T0_T
sys.validate()
# WARNING: variable(s) declared via .add() are also produced by a relation
#   declared value will be overwritten after solve: ['T0_T']
```

2. **Declared variable used by no relation** — orphan / typo:

```python
sys.add("unused_var", 42.0)
sys.validate()
# WARNING: variable(s) declared via .add() are not used by any relation: ['unused_var']
```

Warnings fire once per system instance; suppressed on sweeps/re-solves.

**Still NOT checked:** Whether n_equations == n_unknowns in the general case. An underdetermined system where nothing needs the missing variable still produces no error.

### Gauss-Seidel divergence

**Problem:** Systems with strong coupling (|spectral radius| > 1) diverge regardless of relaxation.

```python
# This ALWAYS diverges — spectral radius >> 1
def r1(x): return {"y": 10*x + 1}
def r2(y): return {"x": 10*y + 1}
sys.use(r1); sys.use(r2)
sys.solve_gauss_seidel(max_iter=20)
# RuntimeError: Not converged after 20 iters (residual: 9.90e+01)
```

**Workaround:** Use `solve_newton()` for strongly coupled systems. Newton converges even when Gauss-Seidel diverges.

### Gauss-Seidel convergence rate

For linear systems, Gauss-Seidel convergence rate is linear (geometric). With `relaxation=ω < 1`, each iteration reduces error by factor ≈ ω × spectral_radius. Heat exchanger example needs 33 iterations; aerodynamic systems may need 100+.

**Workaround for slow convergence:**
1. Try `relaxation=0.5` — more conservative but stable
2. Try `solve_newton()` — quadratic convergence
3. Improve initial guess with `sys.set()` before solving

### `solve_newton` with poor initial guess

Newton's method can diverge if the initial guess is far from the solution:

```python
# Newton on a system with multiple solutions — may find wrong one
sys.set(x=0.0)   # near a saddle point
sys.solve_newton()  # may fail or find wrong root
```

**Workaround:** Use `solve_gauss_seidel()` first to get close, then refine with `solve_newton()`.

### Warm-starting between sweep points — ✓ fixed

`sweep()` now accepts `warm_start=True`. Each successful solve's outputs are carried forward as initial guesses for the next point:

```python
sweep = sys.sweep("UA", np.linspace(500, 5000, 30),
                  method="gauss_seidel", relaxation=0.7,
                  warm_start=True, skip_errors=True)
```

Reduces iteration count significantly for slowly varying parameters. Incompatible with `parallel > 1` (raises `ValueError`).

---

## 2. Quantity Gotchas

### Celsius and Fahrenheit — offset arithmetic ✓ supported (v1.3+)

`degC`, `°C`, `degF`, `°F` are now registered as offset units with full conversion:

```python
Q(25, "degC").si          # 298.15 K — correct
Q(25, "degC").to("K")     # 298.15 K
Q(25, "degC").to("degF")  # 77.00 degF
Q(32, "degF").to("K")     # 273.15 K
```

**Gotcha — arithmetic between offset temperatures:**

```python
Q(100, "degC") + Q(100, "degC")
# SI values: 373.15 + 373.15 = 746.30 K
# → displayed as 746.30 K (not 200°C)
```

Addition/subtraction operates on SI (Kelvin) values. The result has no `_unit_hint`, so it displays in K. This is the correct behaviour for absolute temperature arithmetic — adding two absolute temperatures is physically meaningful only as K. For temperature *differences*, the result is correct. If you need to display the result in °C:

```python
result = Q(100, "degC") + Q(0, "degC")  # purely as K arithmetic
print(result.to("degC"))  # 100.00 degC — force display unit
```

**Gotcha — `"C"` or `"F"` still create custom dimensions:**

```python
Q(25, "C")   # custom dim [C] — NOT Celsius
Q(77, "F")   # custom dim [F] — NOT Fahrenheit
```

Use `"degC"` / `"°C"` / `"degF"` / `"°F"` explicitly.

### Adding scalar to dimensional Q

```python
Q(10, "N") + 5    # ValueError — correct behavior
Q(1.4) + 0.1      # OK — dimensionless
```

The error is correct physics. But it can surprise users who expect implicit dimensionless addition.

### `Q ** non-dimensionless Q`

```python
Q(3, "m") ** Q(2, "N")
# ValueError: Exponent must be dimensionless.
```

Even though the numerical result of `3**2=9` is fine, Anvil refuses because the dimension of `N` makes no physical sense as an exponent.

### Cross-dimension comparison — ✓ fixed

`<`, `<=`, `>`, `>=` between incompatible-dimension Q objects now raise `TypeError`:

```python
Q(10, "N") < Q(5, "K")
# TypeError: Cannot compare [L][M][T-2] < [Θ]: incompatible dimensions.
#            Convert to the same unit first.
```

Previously this returned `NotImplemented`, which Python treated as `True` in boolean contexts — a silent logic bug. `__le__` and `__ge__` operators also added. `==` still returns `False` (not an error) for dimension mismatches.

### `Q(None)` in arithmetic

```python
Q(None, "Pa") + Q(100, "Pa")
# TypeError: unsupported operand type(s) for +: 'NoneType' and 'float'
```

Undefined quantities should never participate in arithmetic. They're only valid as System workspace placeholders.

### Display encoding on Windows

On Windows consoles (cp1252 encoding), printing Dim objects containing Θ (temperature symbol) raises `UnicodeEncodeError`:

```python
print(Q(100, "N") / Q(5, "K"))  # contains [L][M][T-2][Θ-1]
# UnicodeEncodeError: 'charmap' codec can't encode character 'Θ'
```

**Workaround:** Run Python with `-X utf8` flag, or set `PYTHONIOENCODING=utf-8` in environment, or use `repr()` only in contexts you control.

---

## 3. Relation Gotchas

### Functions that don't return a dict — ✓ fixed

```python
def bad(x):
    return x * 2   # not a dict

sys.use(bad)
sys.solve_forward()
# RuntimeError: Relation 'bad' returned 'Quantity' instead of a dict.
#   Relations must return a dict mapping output names to values.
#   Example: return {"result": Q(F, "N")}
```

Previously this silently produced no outputs. Now raises `RuntimeError` with a clear message. Single-scalar return with exactly one known output still works as a narrow convenience.

### Dynamic dict construction

```python
def fn(x, mode):
    d = {}
    if mode == 1:
        d["y"] = x * 2
    else:
        d["z"] = x * 3
    return d   # keys depend on runtime value

sys.use(fn)
```

AST pass can't detect the keys (not in a literal `return {"key": ...}`). Runtime probe with dummy values (mode=1.0) would succeed but might miss the alternate keys. Anvil discovers `y` but not `z` (or vice versa).

**Workaround:** Use explicit return or always return all keys with `None`:

```python
def fn(x, mode):
    return {"y": x*2 if mode == 1 else None,
            "z": x*3 if mode != 1 else None}
```

### Quantity as dict key

```python
def bad_rel(x):
    return {Q(1, "Pa"): x * 2}   # Q is not hashable
# TypeError: cannot use Quantity as dict key
```

Always use string keys.

### NumPy ufuncs break unit propagation

```python
import numpy as np

def fn(T):
    return {"a": np.sqrt(T)}   # np.sqrt(Q) fails → fallback to float → no unit

sys.add("T", 300, "K")
sys.use(fn)
r = sys.solve_forward()
r["a"]   # dimensionless float, no K^0.5 unit
```

**Workaround:** Use Python math or wrap explicitly:

```python
def fn(T):
    T_val = float(getattr(T, "si", T))
    return {"a": Q(T_val ** 0.5, "K^0.5")}
```

---

## 4. Registry Gotchas

### Duplicate push warning

```python
anvil.push(my_func, name="my_rsq")
anvil.push(my_func, name="my_rsq")   # UserWarning: RSQ 'my_rsq' already exists
```

Use `anvil.update()` for intentional overwrites.

### Seed only runs once (or when builtins missing)

After initial seeding, new built-in RSQs added to `seed.py` only appear after:
1. `from anvil.seed import seed; seed(force=True)` — force re-seed
2. Or: new RSQ name added to `_SEED_ENTRIES`, then next import checks if all builtins present

If you add an RSQ to `seed.py` and it doesn't appear in `anvil.R.*`, run `seed(force=True)`.

### Registry DB at `~/.anvil/registry.db`

The global registry is per-user, not per-project. All Anvil sessions on the same machine share the same `~/.anvil/registry.db`. Local RSQs pushed in one script are visible in all other scripts.

**Implication:** `anvil.push()` in a script permanently modifies the shared DB. Use project registries (`anvil.project()`) for development RSQs.

### `anvil.R.<name>` vs string lookup — ✓ fixed

`anvil.push()` and `anvil.update()` now rebuild `anvil.R.*` / `anvil.S.*` / `anvil.QDB.*` automatically. The new RSQ is accessible immediately:

```python
import anvil
anvil.push(my_func, name="new_rsq")
anvil.R.new_rsq(x=1.0)   # works — no restart needed
```

Manual rebuild still available if needed (e.g. after direct DB manipulation):
```python
anvil.registry._rebuild_namespaces()
```

---

## 5. Solver-Specific Limits

### `find_root` — no real root in bracket

```python
solvers.find_root(lambda x: x**2 + 1, bracket=(0, 10))
# ValueError: f(a) and f(b) must have different signs
```

Brent's method requires a sign change. If your function is always positive (or always negative) in the bracket, it cannot find a root.

### `solve_ode` — success flag is unreliable for stiff problems

ODE with singularity may report `success=True`:

```python
r = solvers.solve_ode(lambda t, y: [1.0/(y[0]-0.5)], (0, 0.4), [0.0])
r["success"]   # True — but the solution is garbage
```

**Workaround:** Check `r["message"]` and sanity-check the solution values. For stiff problems, use `solve_ode_stiff()`.

### `solve_pde_heat_1d` — 1D uniform Cartesian only

Limitations:
- 1D only (no 2D/3D)
- Uniform grid only (constant dx)
- Constant diffusivity only (no α(x) or α(T))
- Dirichlet or zero-flux Neumann BCs only (no Robin, mixed, time-derivative BCs)
- Scalar PDE only (no vector equations, no coupled PDEs)

For any of these, use a CLI adapter wrapping OpenFOAM/FEniCS/FiPy.

### `minimize` — local minima only

All methods in `solvers.minimize()` are gradient-based (or simplex-based) local optimizers. They find the nearest local minimum to `x0`.

```python
# Rosenbrock has one global minimum at [1, 1]
r = solvers.minimize(rosen, [0.0, 0.0])   # converges to [1, 1]

# Multi-modal function — result depends on x0
def f(x): return np.sin(x[0]) + 0.1*x[0]**2
r = solvers.minimize(f, [0.0])   # local min near x=0
r = solvers.minimize(f, [-3.0])  # different local min
```

**Workaround:** Use multi-start (run `minimize` from multiple `x0` values), or use `scipy.optimize.differential_evolution` directly for global optimization.

---

## 6. Adapter Limitations

### No `"http"` or `"shared_lib"` backend

Only `"python"` and `"cli"` backends are implemented. HTTP endpoints and shared libraries require custom wrapping.

### CLI adapter timeout kills the whole process tree

`subprocess.run(..., timeout=N)` raises `TimeoutExpired` and terminates the process, but may not clean up child processes. On Windows this can leave orphaned processes.

**Workaround:** Implement cleanup in the `setup` function's try/finally block.

### Thread safety in parallel sweeps

Python backend adapters are called from `ThreadPoolExecutor` threads in parallel sweeps. If the adapter writes to a shared file or modifies global state, race conditions can occur.

**Workaround:** Use `cwd` pointing to separate per-call directories, or use `parallel=1`.

### No state between adapter calls

Each adapter call is stateless. If your external tool requires initialization (connecting to a service, loading large data) per call, it's called every time.

**Workaround:** Implement caching inside the wrapper function using `functools.lru_cache` or module-level state.

---

## 7. Accuracy and Numerical Precision

### Internal precision: float64

All workspace values are `np.float64`. Loss of precision occurs for:
- Very large values combined with very small (cancellation): `Q(1e20, "Pa") - Q(1e20 - 1, "Pa")` → loss of significant digits
- Deeply chained exponentiation: `Q(x, "m") ** 0.5 ** 0.5` — compounding roundoff

### Unit scaling and precision

```python
Q(1, "psi").to("Pa").value
# 6894.757293168  (exact database value)

Q(1, "psi").si
# 6894.757293168  (preserved — no intermediate rounding)
```

Conversion chains can accumulate floating-point errors:

```python
Q(1, "ft").to("cm").to("mm").to("m").si
# ~0.3048000000000001 (small roundoff vs 0.3048 exact)
```

### Solver tolerances vs physical accuracy

| Solver | Default tolerance | Practical accuracy |
|--------|------------------|--------------------|
| `find_root` (brent) | 1e-12 | ~12 significant digits |
| `solve_nonlinear` | 1e-10 | ~10 significant digits |
| `solve_ode` | rtol=1e-8, atol=1e-10 | 6–8 significant digits |
| `solve_ode_stiff` | rtol=1e-6, atol=1e-10 | 4–6 significant digits |
| `solve_bvp` | tol=1e-3 | 2–3 significant digits (coarse mesh) |
| `solve_pde_heat_1d` | dx²/12 spatial, dt²/12 temporal | 0.05% with default settings |
| `minimize` | 1e-8 | 8 significant digits |

### PDE accuracy

Crank-Nicolson is 2nd order in both space and time. With nx=50, nx=100, the spatial error is O(dx²):

```
nx=50:   dx=0.02   spatial error ~ 4e-4
nx=100:  dx=0.01   spatial error ~ 1e-4  (4× improvement = 2× in dx)
nx=200:  dx=0.005  spatial error ~ 2.5e-5
```

---

## 8. Performance Limits

| Operation | Typical time | Hard limit |
|-----------|-------------|------------|
| Single `forward` pass, 5 relations | <1 ms | — |
| `gauss_seidel`, 50 iterations | ~5 ms | — |
| `find_root` (brent) | ~10 µs | — |
| `sweep(50 points)`, simple system | ~50 ms | Memory scales with n_points |
| `sweep(50 points, parallel=4)` | ~15 ms | 4 concurrent solve copies |
| `sensitivity(5 inputs)` | ~10× single solve | — |
| Registry SQLite lookup | ~1 ms | — |
| Project `promote_all(1000 RSQs)` | ~1 s | — |

### Memory

Each sweep point stores a full Result object with all workspace variables. For large systems (100+ variables) × 500 sweep points, this can reach 50–100 MB. Use `sweep.to_dict()` to extract arrays and release.

---

## 9. Known Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| Cross-dim `<`/`<=`/`>`/`>=` silent boolean bug | ✓ **Fixed** | Now raises `TypeError` |
| Non-dict relation return silent no-op | ✓ **Fixed** | Now raises `RuntimeError` |
| `anvil.R.*` stale after `push()` | ✓ **Fixed** | Namespace rebuilt automatically |
| DOF: declared var overwritten with no warning | ✓ **Fixed** | `validate()` warns once per system |
| No warm-start between sweep points | ✓ **Fixed** | `sweep(warm_start=True)` |
| Celsius/Fahrenheit not supported | ✓ **Fixed** (v1.3) | `degC`, `°C`, `degF`, `°F` with full offset arithmetic |
| Seed not updating changed built-in RSQs | ✓ **Fixed** (v1.3) | Source strings compared; changed RSQs re-seed automatically |
| Beam RSQ `max_moment` wrong unit (`"N"` instead of `"N*m"`) | ✓ **Fixed** (v1.3) | Corrected in seed.py |
| `deg` unit not working as angle input to RSQs | ✓ **Fixed** (v1.3) | `_rad()` helper in loader handles both `Q(deg)` and plain float |
| `viz.dependency_graph()` overlaps nodes for large systems | Open | Scale figure: `fig.set_size_inches(20, 15)` |
| `block` relation returns all workspace keys, not just declared outputs | Open | Access only the keys you care about |
| `_qty_compatible` cache resets on `copy()` | Open | Negligible — first call recaches |
| `ResourceWarning: unclosed database` on CPython 3.14+ | Open | Harmless for scripts; `store.close()` in servers |
| Windows cp1252 encoding breaks Dim repr with Θ symbol | Open | Use `-X utf8` flag or `PYTHONIOENCODING=utf-8` |
| `anvil.project()` prints "Project opened" in silent scripts | Open | Redirect stdout if needed |
| `as_relation()` closure re-validates on every call | Open | Avoid composition inside tight loops |
| `solve_ode` `success=True` for singular/ill-conditioned problems | Open | Check `r["message"]`; validate results physically |
| `degC`/`degF` arithmetic result displays in K, not °C | By design | Use `.to("degC")` on result if display unit matters |
| `"C"` or `"F"` (without prefix) create custom dimensions, not Celsius/Fahrenheit | By design | Always use `"degC"` / `"°C"` / `"degF"` / `"°F"` |
