# Advanced Topics

---

## System Composition

Systems can be nested into larger systems via `.as_relation()`. This is Anvil's primary abstraction mechanism for building complex multi-physics tools.

### Pattern: subsystem as relation

```python
# 1. Build and test subsystem independently
nozzle = anvil.system("rocket_nozzle")
nozzle.add("P0", 6.9e6, "Pa")
nozzle.add("T0", 3500, "K")
# ... add relations ...
nozzle.solve_forward()   # verify it works

# 2. Wrap as relation
nozzle_rel = nozzle.as_relation(
    inputs=["P0", "T0", "gamma", "R_gas", "A_throat", "A_exit", "P_amb"],
    outputs=["thrust", "Isp", "mdot", "V_exit"],
)

# 3. Use in larger system
rocket = anvil.system("two_stage")
rocket.add("P0_1", 10e6, "Pa")
rocket.add("T0_1", 3500, "K")
# ... stage 1 nozzle inputs ...
rocket.use(nozzle_rel, map={"P0": "P0_1", "T0": "T0_1"})

# ... add Tsiolkovsky, staging relations, etc. ...
rocket.solve_forward()
```

### How `.as_relation()` works

Creates a closure `_fn(**kwargs)` that:
1. Deep-copies the system
2. For each kwarg, overwrites the corresponding quantity's `_si_value`
3. Calls `sys.copy().solve()`
4. Extracts the declared outputs from the result
5. Returns them as a dict

This means every call to the composed relation runs a full solve of the subsystem. For iterative parent systems, the subsystem is solved at every Gauss-Seidel iteration.

**Performance impact:** For a parent system with 50 Gauss-Seidel iterations and a subsystem that takes 5 ms to solve, composition adds 250 ms per parent solve.

### Pre-built system composition

`anvil.S.rocket_nozzle` is already a System. Use it in composition directly:

```python
nozzle = anvil.S.rocket_nozzle
rel = nozzle.as_relation(outputs=["thrust", "Isp"])

parent = anvil.system("mission")
parent.use(rel)
```

---

## Cyclic Systems — When to Use Each Solver

A system has cycles when relation A's output is relation B's input AND relation B's output is relation A's input (directly or transitively).

```python
sys.validate()
sys._has_cycles      # True or False
sys._exec_order      # list of relation indices in topo order

# Coupled variables (appear in both all_inputs and all_outputs)
all_out = set().union(*[r._outputs for r in sys._relations])
all_in  = set().union(*[r._inputs  for r in sys._relations])
coupled = all_out & all_in
```

| Solver | Use when |
|--------|---------|
| `solve_forward()` | No cycles — validated by `_has_cycles=False` |
| `solve_gauss_seidel()` | Cycles, weakly coupled (convergence factor < 1) |
| `solve_newton()` | Cycles, strongly coupled or slow GS convergence |

### Building cyclic systems manually

```python
# Counter-flow heat exchanger — Q_dot depends on T_hot_out, which depends on Q_dot
sys = anvil.system("hx")
sys.add("T_hot_in",  600, "K")
sys.add("T_cold_in", 290, "K")
sys.add("T_hot_out", 400, "K")   # initial guess for iteration
sys.add("T_cold_out",350, "K")   # initial guess
sys.add("Q_dot",  100000, "W")   # initial guess
sys.add("UA", 2000, "W")

def energy_hot(T_hot_in, T_hot_out, Cp_hot, mdot_hot):
    return {"Q_dot": Cp_hot * mdot_hot * (T_hot_in - T_hot_out)}

def energy_cold(T_cold_in, Q_dot, Cp_cold, mdot_cold):
    return {"T_cold_out": T_cold_in + Q_dot / (Cp_cold * mdot_cold)}

def lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out, UA, Cp_hot, mdot_hot):
    lmtd_val = ((T_hot_in - T_cold_out) - (T_hot_out - T_cold_in)) / \
                np.log((T_hot_in - T_cold_out) / (T_hot_out - T_cold_in))
    Q = UA * lmtd_val
    return {"T_hot_out": T_hot_in - Q / (Cp_hot * mdot_hot)}

sys.use(energy_hot)
sys.use(energy_cold)
sys.use(lmtd)
# Cycles: Q_dot → T_cold_out → energy_hot → Q_dot
#         T_hot_out → lmtd → T_hot_out (self-referential!)

result = sys.solve_gauss_seidel(relaxation=0.5, monitor=True)
```

**Initial guesses matter:** GS starts with declared values. Good guesses near the solution converge faster.

---

## Block Relations

`Relation.block()` chains multiple functions into a single relation that shares an intermediate workspace.

### Use cases

1. **Breaking up complex physics** — separate concerns into testable steps:

```python
def compute_isentropic(M, gamma=1.4):
    T_ratio = 1 + (gamma-1)/2 * M**2
    P_ratio = T_ratio ** (gamma/(gamma-1))
    return {"T0_T": T_ratio, "P0_P": P_ratio}

def compute_exit(T0, P0, T0_T, P0_P, gamma, R_gas):
    T_e = T0 / T0_T; P_e = P0 / P0_P
    a_e = (gamma * R_gas * T_e) ** 0.5
    return {"T_exit": Q(T_e, "K"), "P_exit": Q(P_e, "Pa"), "a_exit": Q(a_e, "m/s")}

def compute_thrust(mdot, V_exit, P_exit, P_amb, A_exit):
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    return {"thrust": Q(F, "N")}

nozzle_block = Relation.block("nozzle_physics",
    steps=[compute_isentropic, compute_exit, compute_thrust])
```

2. **Avoiding intermediate workspace pollution** — block outputs are scoped:

If step 1 outputs `T0_T` and step 2 also outputs `T0_T` (corrected), only step 2's value appears in the parent workspace.

### Block relation input detection

`Relation.block()` computes:
- `all_inputs`: parameters of all steps NOT produced by any earlier step
- `all_outputs`: keys returned by any step

```python
nozzle_block._inputs
# ['A_exit', 'A_throat', 'P0', 'T0', 'gamma', 'R_gas', 'P_amb', 'mdot']
# (initial inputs to the chain — not produced by any step)

nozzle_block._outputs
# ['T0_T', 'P0_P', 'T_exit', 'P_exit', 'a_exit', 'thrust']
# (all keys produced by any step)
```

**Gotcha:** The block always returns ALL workspace keys (including inputs passed through). Filter on the caller side:

```python
r = nozzle_block(M=3.0, T0=3500, P0=10e6, ...)
r["thrust"]   # the output you want
r["M"]        # also present — the input passed through
```

---

## `anvil.relation` Decorator Details

The `@anvil.relation` decorator wraps the function AND (by default) registers it in the global registry.

```python
@anvil.relation(domain="aero", tags=["compressible"], register=True)
def my_rsq(M, gamma=1.4):
    return {"T_ratio": 1 + (gamma-1)/2*M**2}

# my_rsq is now a Relation object (not the original function)
my_rsq(M=2.0)           # direct call — returns dict
my_rsq._inputs          # ['M', 'gamma']
my_rsq.name             # "my_rsq"
anvil.R.my_rsq(M=2.0)  # also works via registry
```

Without parentheses:
```python
@anvil.relation
def simple_fn(x, y):
    return {"z": x + y}
# Registered with name "simple_fn", no domain, no tags
```

`register=False` — wrap without pushing to registry:
```python
@anvil.relation(domain="draft", register=False)
def draft(x): return {"y": x*2}
# draft is a Relation but NOT in anvil.R.*
```

**Important:** If registration fails (e.g., DB error), the relation still works as a callable — `push()` failure is non-fatal by design.

---

## Watchdog

`anvil.Watchdog` is an internal convergence monitoring utility. It tracks residuals per iteration and can trigger callbacks.

```python
from anvil.watchdog import Watchdog

wd = Watchdog(rtol=1e-6, max_iter=200)
for i in range(max_iter):
    prev = current.copy()
    # ... update ...
    converged, residual = wd.check(prev, current)
    if converged:
        break
```

This is used internally by the monitor mode of `solve_gauss_seidel`. Direct use is uncommon unless you're building custom iterative algorithms.

---

## CFD Module

`anvil.cfd` is a 2D finite-volume Euler solver for structured body-fitted meshes. It handles subsonic through supersonic flows with Roe/HLLC flux schemes, MUSCL reconstruction, and multiple BC types.

See **[CFD Solver](18)** for the full reference: mesh factories, boundary conditions, solver parameters, post-processing, VTK/Tecplot export, and System integration via `solver.as_relation()`.

```python
from anvil.cfd import CFDSolver, Mesh
from anvil.cfd.bc import SupersonicInlet, SlipWall, SupersonicOutlet, Farfield

mesh   = Mesh.wedge(half_angle_deg=10, chord=1.0, height=0.8, nx=80, ny=40)
bcs    = {"west": SupersonicInlet(M=2.0, p=101325, T=300),
          "east": SupersonicOutlet(), "south": SlipWall(),
          "north": Farfield(M=2.0, p=101325, T=300)}
solver = CFDSolver(mesh, bcs, flux_scheme="roe", order=2, cfl=0.5)
solver.initialize(M=2.0, p=101325, T=300)
result = solver.run(max_iter=5000, tol=1e-6, monitor=True)
result.to_vtk("wedge.vtk")

# Integrate into an Anvil System
rel = solver.as_relation(inputs=["M_inf","p_inf","T_inf"], outputs=["CL","CD"])
```

---

## `anvil.help_.lookup()` — In-REPL Reference

```python
anvil.lookup("pressure")
# Searches registry + constants + fluids + materials for "pressure"
# Prints matching RSQs, constants, fluid properties
```

A convenience function for interactive use — equivalent to `anvil.search()` with more complete output.

---

## Custom Unit Registration

The UnitDB is extensible. Register new units at module level before any `Q` creation:

```python
from anvil.units import db, Dim

# Register a new unit
db.register("furlong", 201.168, Dim(L=1))     # 1 furlong = 201.168 m
db.register("fortnight", 1209600.0, Dim(T=1)) # 1 fortnight = 2 weeks in seconds

Q(3, "furlong")                    # Q(3, "furlong") — si = 603.504 m
Q(1, "furlong/fortnight")          # Q(1, "furlong/fortnight") — velocity
Q(1, "furlong/fortnight").to("m/s")  # conversion
```

Set as preferred display unit:
```python
from anvil.units import Dim
db.set_preferred(Dim(L=1), "furlong", "furlong")  # set as preferred SI AND Imperial
```

**Caution:** Custom units added at runtime are not persisted — re-register each session.

---

## Building a Multi-Stage Analysis Pipeline

Pattern for complex workflows:

```python
import anvil
from anvil import Q
import numpy as np

# Stage 1: Combustion chamber equilibrium (Cantera adapter or simple model)
@anvil.relation(domain="propulsion.combustion")
def combustion(OF, Pc_bar, fuel="H2", oxidizer="O2"):
    Pc = Pc_bar * 1e5
    Tc = 3400.0 * (1 - 0.02*abs(OF-6)) - 0.001*(Pc-10e6)
    gamma = 1.2 + 0.01*(OF-6)
    R_gas = 8.314 / 0.007   # H2/O2 approx
    return {"Tc": Q(Tc, "K"), "gamma_c": gamma, "R_gas_c": Q(R_gas, "J/kg/K")}

# Stage 2: Nozzle (pre-built system)
nozzle = anvil.S.rocket_nozzle.copy()
nozzle_rel = nozzle.as_relation(
    inputs=["P0", "T0", "gamma", "R_gas", "A_throat", "A_exit", "P_amb"],
    outputs=["thrust", "Isp", "mdot"],
)

# Stage 3: Vehicle performance
@anvil.relation(domain="propulsion.trajectory")
def delta_v_calc(Isp, mass_wet, mass_dry):
    g0 = 9.80665
    return {"delta_v": Q(g0 * Isp * np.log(mass_wet / mass_dry), "m/s")}

# Wire together
pipeline = anvil.system("engine_sizing")
pipeline.add("OF",       6.0)
pipeline.add("Pc_bar",   100.0)
pipeline.add("A_throat", 0.01,  "m^2")
pipeline.add("A_exit",   0.1,   "m^2")
pipeline.add("P_amb",    0.0,   "Pa")  # vacuum
pipeline.add("mass_wet", 100000, "kg")
pipeline.add("mass_dry",  20000, "kg")

pipeline.use(combustion)
pipeline.use(nozzle_rel, map={
    "P0": "Pc",       # combustion outputs Pc
    "T0": "Tc",
    "gamma": "gamma_c",
    "R_gas": "R_gas_c",
})
pipeline.use(delta_v_calc)

result = pipeline.solve_forward()
print(f"Thrust: {result['thrust'].to('kN')}")
print(f"Isp: {result['Isp']}")
print(f"ΔV: {result['delta_v'].to('km/s')}")

# Sweep: find optimal OF ratio
sweep = pipeline.sweep("OF", np.linspace(4, 8, 20))
sweep.summary(outputs=["thrust", "Isp", "delta_v"])
```

---

## Registry Loader — How RSQs Are Reconstituted

`anvil.registry.loader.load_rsq(record, store)` takes a registry record (dict from SQLite) and returns a live Python object.

**For Relations (type "R"):**
1. Source code string retrieved from `record["source"]`
2. `exec()` in a namespace with `anvil`, `Q`, `solvers`, `np` pre-imported
3. Looks for `export` variable in the namespace — this is the callable
4. Wraps in `Relation(export)`

```python
# seed.py stores source as:
'def isentropic_ratios(M, gamma=1.4):\n    ...\nexport = isentropic_ratios'

# loader does:
namespace = {"anvil": anvil, "Q": Q, "np": np, "solvers": solvers}
exec(source, namespace)
func = namespace["export"]
rel = Relation(func)
```

**For Systems (type "S"):**
Source is a serialized `anvil.system(...)` construction script. Executed similarly.

**For Quantities (type "Q"):**
Source is `export = Q(value, "unit")`. Executed to get the Q object.

**Security note:** Registry sources are executed with `exec()`. The global registry (`~/.anvil/registry.db`) can contain arbitrary code. Do not open unknown registry files or accept untrusted registry records.
