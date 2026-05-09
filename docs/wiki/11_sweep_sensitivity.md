# Sweep & Sensitivity

---

## Parametric Sweep

`sys.sweep()` evaluates the system at multiple values of one parameter and collects all results.

```python
sweep = sys.sweep(
    param_name,           # str — must be in sys._quantities
    values,               # array-like of parameter values (in original declared unit)
    skip_errors=False,    # True: failed points → None instead of raising
    parallel=1,           # int > 1: concurrent evaluation via ThreadPoolExecutor
    warm_start=False,     # True: carry computed outputs forward as initial guess
    **solve_kwargs,       # passed to sys.solve(): method, relaxation, max_iter, …
)
```

**Returns:** `SweepResult` object.

### Parameter requirement

The parameter must be declared with `.add()` before sweeping. The values are interpreted in the original declared unit:

```python
sys.add("P0", 6.9e6, "Pa")
# sweep in Pa (SI)
sweep = sys.sweep("P0", np.linspace(5e6, 30e6, 20))

sys.add("T", 300, "K")
# values in K — not Rankine, not Celsius
sweep = sys.sweep("T", np.linspace(200, 600, 20))
```

If you try to sweep a name not in the system:
```python
sys.sweep("nonexistent", values)
# KeyError: "Cannot sweep 'nonexistent' -- not in system.
#   Available inputs: P0, T0, gamma, ...
#   Hint: use system.add('nonexistent', value) first."
```

### Warm-start

For iterative systems (Gauss-Seidel/Newton) sweeping over a slowly varying parameter, `warm_start=True` carries the previous point's computed outputs forward as initial guesses. This reduces iteration count significantly when adjacent points are close together.

```python
# Without warm_start: every point starts from declared initial guesses
# With warm_start:    each point starts from previous solution

sweep = sys.sweep("UA", np.linspace(500, 5000, 30),
                  method="gauss_seidel", relaxation=0.7,
                  warm_start=True)
```

**Restrictions:**
- Incompatible with `parallel > 1` — raises `ValueError` (parallel order is undefined)
- Only updates quantities declared with `.add()`, not purely computed intermediates
- If a warm-started point fails and `skip_errors=True`, that point's guess is not carried forward

### Solver options in sweep

```python
# Coupled system — use GS with relaxation
sweep = sys.sweep("UA", np.linspace(500, 5000, 20),
                  method="gauss_seidel", relaxation=0.7, max_iter=100)

# Newton for strongly nonlinear
sweep = sys.sweep("P0", values, method="newton", rtol=1e-10)
```

### Parallel sweep

```python
# Uses ThreadPoolExecutor — best for NumPy/SciPy heavy relations
sweep = sys.sweep("M", np.linspace(0.5, 3.0, 50), parallel=4)
```

Each parallel point gets its own deep copy of the system (`sys.copy()`), so state doesn't collide. Result order is preserved (indexed by original value order, not completion order).

**Practical gains:**
- Pure Python arithmetic in relations: minimal speedup (GIL)
- NumPy/SciPy operations (find_root, matrix math, integrations): near-linear speedup up to ~4 workers

**Thread safety requirement:** All Relation functions called in parallel sweep must be thread-safe. Pure functions with no global state are safe. Adapters that write to a shared directory are not.

### Error handling

```python
sweep = sys.sweep("q_heat", np.linspace(0, 1e6, 50), skip_errors=True)
# Points where flow chokes (ValueError) → None in results, UserWarning printed
sweep.summary()  # failed points shown as "(failed)"
```

Without `skip_errors=True` (default), the first failure raises `RuntimeError` with the failed point's value.

---

## SweepResult

### Accessing results

```python
sweep["thrust"]    # numpy array of SI floats, length n_points
sweep["P0"]        # numpy array of parameter values
sweep["M2"]        # numpy array of output values

# To convert output values: use Q
from anvil import Q
thrust_kn = sweep["thrust"] / 1000   # manual conversion
```

### `.summary()`

```python
sweep.summary(outputs=["thrust", "Isp", "mdot"])
```

**Output example:**
```
----------------------------------------------------------------------
  rocket_nozzle -- sweep over P0
----------------------------------------------------------------------
              P0         thrust            Isp           mdot
            [Pa]            [N]            [s]         [kg/s]
  ----------------------------------------------------------------------
         5000000     2.363e+04          268.3          8.986
     6.579e+06     3.116e+04          269.8          11.84
         8.158e+06     3.869e+04          271.3          14.69
         9.737e+06     4.622e+04          272.8          17.54
     1.132e+07     5.375e+04          274.3          20.39
----------------------------------------------------------------------
```

### `.to_dict(si=True)`

```python
d = sweep.to_dict(si=True)   # dict of numpy arrays, SI values
d["thrust"]   # np.array([23630., 31160., ...])

d = sweep.to_dict(si=False)  # dict of numpy arrays, display-unit values
```

### `.to_csv()` and `.to_json()`

```python
sweep.to_csv("sweep.csv")
sweep.to_csv("sweep.csv", si=True, outputs=["thrust", "Isp"])

sweep.to_json("sweep.json")
```

CSV format: one column per variable, one row per sweep point.

### Jupyter display

`SweepResult` renders as an HTML table in Jupyter. First 8 outputs shown. Units row below headers.

---

## Sensitivity Analysis

`sys.sensitivity()` computes how each output changes relative to each input.

```python
sens = sys.sensitivity(
    outputs=None,     # list of output names; None = all computed outputs
    step=0.01,        # fractional perturbation (1% default)
)
```

**Algorithm:** Central finite difference, normalized:

```
sensitivity[out][inp] = (∂out/∂inp) × (inp/out)
```

A value of 1.0 means a 1% change in `inp` → 1% change in `out`.
A value of 3.0 means a 1% change in `inp` → 3% change in `out`.
Negative values: inverse relationship.

**Computation:** For each input with non-zero value:
1. Perturb `inp` by `+step*|inp|` → solve → get `out_plus`
2. Perturb `inp` by `-step*|inp|` → solve → get `out_minus`
3. `sens = (out_plus - out_minus) / (2*delta) * inp / out_base`

### Example

```python
sys = anvil.system("isentropic")
sys.add("M", 2.0)
sys.add("gamma", 1.4)
sys.use("isentropic_ratios")

sens = sys.sensitivity(outputs=["P0_P", "T0_T"])
sens.summary()
```

**Output:**
```
============================================================
  isentropic -- Sensitivity Analysis
============================================================
  (normalized: 1.0 = 1% input change -> 1% output change)

  P0_P:
    M                     +3.1116  ################
    gamma                 +0.3013  ##

  T0_T:
    M                     +1.4000  #######
    gamma                 +0.5000  ##
============================================================
```

Interpretation for `P0_P`:
- `M`: Mach has 3.1× leverage on P0/P — a 1% increase in M → ~3.1% increase in P0/P
- `gamma`: γ has ~0.3× leverage — relatively insensitive

### `sens.top(output, n=5)`

```python
top5 = sens.top("P0_P", n=5)
# [("M", 3.1116), ("gamma", 0.3013)]
```

Returns a sorted list of `(input_name, sensitivity_value)`, highest absolute value first.

### `sens.to_dict()`

```python
d = sens.to_dict()
# {"P0_P": {"M": 3.1116, "gamma": 0.3013},
#  "T0_T": {"M": 1.4000, "gamma": 0.5000}}
```

### SensitivityResult Jupyter display

Renders as an HTML table with horizontal bar charts for each sensitivity value. Color: blue for positive, red for negative.

---

## Combining Sweep and Sensitivity

Typical workflow: use sweep to understand parameter ranges, then sensitivity to know which inputs matter most.

```python
import numpy as np

# 1. Sweep to find interesting operating points
nozzle = anvil.S.rocket_nozzle.copy()
sweep = nozzle.sweep("P0", np.linspace(5e6, 20e6, 20))
sweep.summary(outputs=["thrust", "Isp"])

# 2. Set to a specific point
nozzle.set(P0=12e6)
result = nozzle.solve_forward()

# 3. Sensitivity at that point
sens = nozzle.sensitivity(outputs=["thrust", "Isp"])
sens.summary()

# 4. Top drivers
print("Top drivers for Isp:")
for name, val in sens.top("Isp", n=3):
    print(f"  {name}: {val:+.3f}")
```

---

## SweepResult Internals

`SweepResult` stores:
- `_param`: parameter name
- `_values`: list of parameter values
- `_results`: list of `Result` objects (or `None` for failed points)
- `_output_keys`: list of output names from first valid result

`sweep["key"]` iterates `_results`, extracting `r[key]._si_value` (or float) per point. For failed points it inserts `np.nan`.

**Memory:** Each result stores the full workspace. For large systems and many points, `SweepResult` can use significant memory. Use `to_dict()` to extract only the arrays you need, then let the result be garbage-collected.

---

## Performance

| Scenario | Time estimate |
|----------|--------------|
| `sweep(n=50)`, forward-pass system, single thread | ~50 × single_solve_time |
| `sweep(n=50, parallel=4)`, scipy-heavy relations | ~15 × single_solve_time |
| `sensitivity(5 inputs, 1 output)` | ~10 × single_solve_time (2 solves per input) |
| `sensitivity(5 inputs, 5 outputs)` | ~10 × single_solve_time (outputs evaluated in same solves) |

`sensitivity()` always runs single-threaded. The number of outputs doesn't increase the number of solves — they all come from the same +/- perturbation runs.
