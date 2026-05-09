# Relation

A `Relation` is a computation block: it accepts keyword arguments and returns a `dict` of outputs. It's the fundamental "equation" unit in Anvil.

---

## Rules for Relation Functions

Every function used as a Relation must:
1. Accept **all inputs as keyword arguments** (no positional-only args)
2. Return a **`dict`** mapping output names (strings) to values
3. Return `Q(value, "unit")` for dimensional outputs — this enables unit propagation
4. Default parameter values work: `def fn(M, gamma=1.4):`

```python
from anvil import Q

def nozzle_thrust(mdot, V_exit, P_exit, P_amb, A_exit):
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    return {"thrust": Q(F, "N")}

def isentropic(M, gamma=1.4):
    T_ratio = 1 + ((gamma - 1) / 2) * M**2
    P_ratio = T_ratio ** (gamma / (gamma - 1))
    return {"T0_T": T_ratio, "P0_P": P_ratio}
```

---

## Creating Relations

### 1. Implicit — `system.use(func)`

The most common approach. The System wraps any callable automatically:

```python
import anvil

def lift(rho, V, S_ref, CL):
    return {"lift": Q(0.5 * rho * V**2 * S_ref * CL, "N")}

sys = anvil.system("wing")
sys.add("rho", 1.225, "kg/m^3")
sys.add("V", 80, "m/s")
sys.add("S_ref", 20, "m^2")
sys.add("CL", 0.5)
sys.use(lift)
```

### 2. Explicit — `Relation(func, **options)`

```python
from anvil.relation import Relation

thrust_rel = Relation(
    nozzle_thrust,
    name="nozzle_thrust",
    tags=["propulsion", "nozzle"],
    desc="Rocket thrust from momentum and pressure.",
)

print(thrust_rel._inputs)   # ['mdot', 'V_exit', 'P_exit', 'P_amb', 'A_exit']
print(thrust_rel._outputs)  # [] — discovered on first call
thrust_rel(mdot=10, V_exit=3000, P_exit=50000, P_amb=0, A_exit=0.5)
print(thrust_rel._outputs)  # ['thrust']
```

### 3. Decorator — `@anvil.relation`

```python
@anvil.relation(domain="propulsion", tags=["nozzle"])
def rocket_thrust(mdot, V_exit, P_exit, P_amb, A_exit):
    """Rocket thrust from momentum and pressure terms."""
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    return {"thrust": Q(F, "N")}

# Now callable via anvil.R.rocket_thrust and usable in any system
r = anvil.R.rocket_thrust(mdot=10, V_exit=3000, P_exit=50000, P_amb=0, A_exit=0.5)
print(r["thrust"])  # 30000.00 N
```

Without parentheses (no metadata):

```python
@anvil.relation
def speed_of_sound(gamma, R_gas, T):
    return {"a": Q((gamma * R_gas * T) ** 0.5, "m/s")}
```

`register=False` — wrap without pushing to registry:

```python
@anvil.relation(domain="test", register=False)
def draft_relation(UA, C_min):
    return {"NTU": UA / C_min}
```

### 4. Block Relation — `Relation.block()`

Groups multiple functions into a single Relation that shares a workspace. Each step's outputs become available to subsequent steps.

```python
from anvil.relation import Relation
from anvil import Q

def area_ratio(A_exit, A_throat):
    return {"area_ratio": A_exit / A_throat}

def mach_from_area(area_ratio, gamma=1.4):
    from anvil import solvers
    def residual(M):
        t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)
        return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio
    M = solvers.find_root(residual, bracket=(1.001, 30.0))
    return {"M_exit": M}

def exit_velocity(M_exit, T0, gamma=1.4, R_gas=287.0):
    T0_T = 1 + (gamma-1)/2 * M_exit**2
    T_e = T0 / T0_T
    a_e = (gamma * R_gas * T_e) ** 0.5
    V = M_exit * a_e
    return {"V_exit": Q(V, "m/s"), "T_exit": Q(T_e, "K")}

nozzle_chain = Relation.block("nozzle_physics",
    steps=[area_ratio, mach_from_area, exit_velocity],
    tags=["propulsion", "nozzle"],
)

print(nozzle_chain._inputs)   # ['A_exit', 'A_throat', 'T0', 'R_gas', 'gamma']
print(nozzle_chain._outputs)  # ['M_exit', 'T_exit', 'V_exit', 'area_ratio']

r = nozzle_chain(A_exit=0.08, A_throat=0.01, T0=3500, gamma=1.25, R_gas=320)
print(r["M_exit"])    # ~3.3
print(r["V_exit"])    # ~2600 m/s
```

**How block works internally:**
1. Calls each step function in order
2. Merges step outputs into a shared workspace dict
3. Each step sees all previously computed values
4. Quantities in the workspace are extracted to SI floats before passing to next step
5. Returns the full workspace as the final dict

**Caveat:** Block relations strip units from intermediate Quantity results (converted to SI floats). The final outputs that are Q objects are preserved.

---

## Input / Output Detection

### Inputs

Detected at construction time by inspecting the function signature:

```python
import inspect
sig = inspect.signature(func)
inputs = list(sig.parameters.keys())
defaults = {k: p.default for k, p in sig.parameters.items()
            if p.default is not inspect.Parameter.empty}
```

All parameters become inputs. Parameters with defaults become optional.

### Outputs

Detected lazily (on first call or during System validation). Two-pass strategy in `_discover_outputs()`:

**Pass 1 — AST inspection** (preferred, avoids side effects):
```python
import ast, inspect
source = inspect.getsource(func)
tree = ast.parse(source)
# Walk return statements, collect string keys from dict literals
```

This works for plain `return {"key": value}` statements. Fails if the dict is constructed dynamically (e.g., `d = {}; d["key"] = val; return d`).

**Pass 2 — Runtime probe** (fallback):
Calls the function with `1.0` for every unknown input. Reads the returned dict keys. Can fail if the function raises with dummy inputs (e.g., division by zero, domain errors).

**Implication:** If output detection fails silently, the Relation has `_outputs = []` and downstream relations that need those outputs will fail at validation.

---

## Relation Object Properties

```python
rel = Relation(func)

rel.name        # str — function name or explicitly set
rel.func        # the callable
rel._inputs     # list of input parameter names
rel._outputs    # list of output dict keys (populated lazily)
rel._defaults   # dict of default values
rel.tags        # list of search tags
rel.desc        # description string
rel.info()      # formatted print of inputs/outputs/tags
```

---

## Calling a Relation Directly

```python
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
# Returns the raw dict — same as calling the function

r["T0_T"]   # 1.8
r["P0_P"]   # 7.8244
```

Defaults are filled automatically:

```python
r = anvil.R.isentropic_ratios(M=2.0)  # gamma=1.4 from default
```

---

## Unit Propagation in Relations

When a System calls a Relation, it tries to pass `Quantity` objects instead of raw floats. If the function's arithmetic is compatible (uses `+`, `-`, `*`, `/`, `**` on Q objects), units propagate through to the outputs.

If the function raises when receiving Q objects (e.g., calls a NumPy ufunc directly on a Q), the system falls back to passing raw SI floats. This is cached per-relation on `rel._qty_compatible`.

```python
def good(F, A):
    return {"sigma": F / A}    # Q/Q → Quantity with Pa dim

def bad_numpy(x):
    import numpy as np
    return {"y": np.sqrt(x)}  # np.sqrt(Q) fails → falls back to float
```

In `bad_numpy`, the output `y` will be a plain float — no unit. It will display with the raw dimension `dimensionless` since no dim info is attached.

---

## Name Mapping

When a Relation's parameter names don't match the System workspace, use `map=`:

```python
# isentropic_ratios expects 'M' but workspace has 'M_exit'
sys.use("isentropic_ratios", map={"M": "M_exit"})

# Map is {relation_param: workspace_name}
```

The mapping creates a wrapper function that translates names before calling the original.

---

## What Can Go Wrong

### Function returns non-dict

```python
def bad(x):
    return x * 2   # not a dict

sys.use(bad)
sys.solve_forward()
# RuntimeError: Relation 'bad' returned 'Quantity' instead of a dict.
#   Relations must return a dict mapping output names to values.
#   Example: return {"result": Q(F, "N")}
```

Always return `{"output_name": value}`.

**Exception — single-output convenience:** If a relation has exactly one known output and returns a bare scalar, Anvil accepts it silently. This is narrow; prefer dict returns.

### Quantity as dict key

```python
def bad_keys(x):
    return {Q(1, "Pa"): x * 2}   # Q as key

# Q is not hashable → TypeError: cannot use Quantity as dict key
# System solve crashes with TypeError
```

### Non-keyword arguments

```python
def bad_positional(x, y, /):   # positional-only (Python 3.8+)
    return {"z": x + y}

# Relation wraps it, but calling with **kwargs → TypeError
# inspect.signature() still captures the names, but calling fails
```

### Side effects in relations

Relations should be pure functions. Side effects (file I/O, global state) in iterative solvers (Gauss-Seidel, Newton) cause N calls per iteration — the side effect runs N × max_iter times.
