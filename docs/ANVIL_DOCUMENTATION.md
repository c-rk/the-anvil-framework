# Anvil Framework Documentation

**Version 1.1.0** | From equations to engineering tools

---

## Table of Contents

1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Core Primitives](#4-core-primitives)
5. [Unit Engine](#5-unit-engine)
6. [System Operations](#6-system-operations)
7. [Solvers](#7-solvers)
8. [Parametric Sweep & Sensitivity](#8-parametric-sweep--sensitivity)
9. [RSQ Registry](#9-rsq-registry)
10. [Built-in RSQs — Full List](#10-built-in-rsqs--full-list)
11. [Adapter Layer](#11-adapter-layer)
12. [Project Registry](#12-project-registry)
13. [Visualization](#13-visualization)
14. [Result Objects](#14-result-objects)
15. [API Reference Summary](#15-api-reference-summary)

---

## 1. Overview

Anvil is a computation framework for engineering and scientific research. Write physics as plain Python functions, wire them into solvable systems, and get results with correct units — automatically.

**Three primitives:**

- **Quantity (Q)** — a number with physical dimensions and units; stores SI internally
- **Relation (R)** — a computation block: keyword inputs → dict of outputs
- **System (S)** — a graph of Quantities and Relations that solves itself

A solved System can become a Relation inside a larger System. This recursive composition lets you build complex multi-physics tools from simple, individually testable pieces.

**Dependencies:** Python 3.10+, NumPy, SciPy. Optional: matplotlib, cantera, jupyter.

---

## 2. Installation

```bash
# Editable install from source
cd anvil-03-1
pip install -e .

# Or add src/ to path directly
import sys
sys.path.insert(0, "path/to/anvil-03-1/src")
import anvil
```

**Install all dependencies:**

```bash
pip install numpy scipy matplotlib jupyter
conda install -c cantera cantera   # optional — combustion adapter
```

---

## 3. Quick Start

```python
import anvil
from anvil import Q, K, Pa, m, s, kg

# Direct call — no System needed
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
print(r["P0_P"])   # 7.824

# Load a pre-built System, override, solve
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=10e6, T0=3200)
result = nozzle.solve_forward()
result.summary()

# Build your own System
sys = anvil.system("wing_loading")
sys.add("W",     50000, "N")
sys.add("S_ref", 20,    "m^2")
sys.add("V",     80,    "m/s")
sys.add("rho",   1.225, "kg/m^3")

def lift_coeff(W, S_ref, V, rho):
    q = 0.5 * rho * V**2
    CL = W / (q * S_ref)
    return {"q_inf": Q(q, "Pa"), "CL": CL}

sys.use(lift_coeff)
sys.solve_forward().summary()
```

---

## 4. Core Primitives

### 4.1 Quantity

A numerical value with physical dimensions. Stores SI internally; displays in the unit you specified.

```python
from anvil import Q

# Create — three equivalent styles
p = Q(101325, "Pa")
p = Q(101325, "pressure")        # category alias → resolves to Pa
p = Q(101325, "[L-1][M][T-2]")  # raw dimension notation

# Unit-stub syntax (cleanest)
from anvil import K, Pa, m, s, kg, mol, N, J, W
from anvil import km, cm, mm, g, kPa, MPa, GPa, bar, atm, psi
from anvil import kN, kJ, MJ, kW, BTU, ft, inch, in_, lb, lbf, hr

T   = 300 * K           # Q(300, "K")
P   = 101325 * Pa       # Q(101325, "Pa")
v   = 340 * (m/s)       # Q(340, "m/s")
g   = 9.81 * m/s**2     # Q(9.81, "m/s^2")
rho = 1.225 * kg/m**3   # Q(1.225, "kg/m^3")
```

**Compound units are parsed automatically:**

```python
mdot = Q(1.5, "g/s")       # parsed: 1.5 × 1e-3 kg/s
vol  = Q(5,   "cm**3")     # parsed: 5 × 1e-6 m^3
flux = Q(200, "W/m^2")     # parsed directly
visc = Q(1e-3,"Pa*s")      # known unit
```

**Compact dimension notation:**

```python
# Both forms are equivalent
d1 = Q(1, "[L][M][T-2]")   # standard
d2 = Q(1, "[LMT-2]")       # compact — same dimension
```

**Arithmetic propagates dimensions:**

```python
F = Q(100, "N")
A = Q(0.01, "m^2")
sigma = F / A              # → Q(10000, "Pa")  [auto-detected]

E_kin = 0.5 * Q(10, "kg") * Q(30, "m/s")**2   # → J
P_out = Q(1000, "J") / Q(2, "s")               # → W
```

**Properties and methods:**

```python
q.value         # display value (in original unit)
q.si            # SI float
q.unit          # display unit string
q.dim           # Dim object
q.dimensionless # bool

q.to("kPa")     # unit conversion — returns new Quantity
q.in_bounds()   # check against bounds if set
```

**Note on `in` (inches):** `in` is a Python keyword. Use `inch` or `in_` as the unit stub. `Q(5, "in")` still works as a string argument.

```python
from anvil import inch, in_
length = 5 * inch        # or 5 * in_
```

### 4.2 Relation

A computation block — any Python function that accepts keyword arguments and returns a dict.

```python
from anvil import Q

def nozzle_thrust(mdot, V_exit, P_exit, P_amb, A_exit):
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    return {"thrust": Q(F, "N")}
```

**Rules:**
- Accept all inputs as keyword arguments (no positional args)
- Return a `dict` mapping output names to values
- Return `Q(value, "unit")` objects for dimensional outputs — this propagates units automatically
- Default parameter values work normally: `def fn(M, gamma=1.4):`

**Registration decorator:**

```python
@anvil.relation(domain="propulsion", tags=["nozzle"])
def thrust_eq(mdot, V_exit, P_exit, P_amb, A_exit):
    """Rocket thrust from momentum and pressure terms."""
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    return {"thrust": Q(F, "N")}
```

**Block relation** — multiple functions in sequence sharing a workspace:

```python
from anvil.relation import Relation

nozzle_chain = Relation.block("nozzle_physics",
    steps=[area_ratio_fn, mach_fn, isentropic_fn, thrust_fn],
    tags=["propulsion", "nozzle"],
)
system.use(nozzle_chain)
```

**Unit propagation note:** When all inputs to a relation have known dimensions (i.e., they are Quantity objects), the framework passes Quantities to the function. Functions that use standard Python arithmetic (`+`, `-`, `*`, `/`, `**`) will automatically propagate units through to their outputs. Functions that call NumPy ufuncs directly on inputs fall back to receiving raw SI floats.

### 4.3 System

A solvable engineering problem: a named set of Quantities wired to Relations.

```python
nozzle = anvil.system("rocket_nozzle")
nozzle.add("P0", 6.9e6, "Pa")
nozzle.add("T0", 3500,  "K")
nozzle.use(area_ratio_fn)
nozzle.use(thrust_fn)
result = nozzle.solve_forward()
result.summary()
```

---

## 5. Unit Engine

### 5.1 How It Works

Every Quantity carries a `Dim` object alongside its numerical value. Dim tracks physical dimensions as a dict of exponents and propagates through all arithmetic:

```
Q(10, "kg") * Q(9.81, "m/s^2")
  value: 10 * 9.81 = 98.1
  dim:   [M] * [L][T-2] → [L][M][T-2]
  lookup: [L][M][T-2] → "N"
  result: 98.1 N
```

If no named unit exists for the resulting dimension, the raw dimension is shown: `[L2][M][T-2][TH-1]`. Computation never fails because of a missing unit name.

### 5.2 Dimension Categories

| Category             | Dimension         | SI unit  |
|----------------------|-------------------|----------|
| `length`             | [L]               | m        |
| `area`               | [L2]              | m^2      |
| `volume`             | [L3]              | m^3      |
| `mass`               | [M]               | kg       |
| `time`               | [T]               | s        |
| `temperature`        | [TH]              | K        |
| `velocity`           | [L][T-1]          | m/s      |
| `acceleration`       | [L][T-2]          | m/s^2    |
| `force`              | [L][M][T-2]       | N        |
| `pressure` / `stress`| [L-1][M][T-2]     | Pa       |
| `energy`             | [L2][M][T-2]      | J        |
| `power`              | [L2][M][T-3]      | W        |
| `density`            | [L-3][M]          | kg/m^3   |
| `frequency`          | [T-1]             | Hz       |
| `mass_flow`          | [M][T-1]          | kg/s     |
| `specific_energy`    | [L2][T-2]         | J/kg     |
| `specific_heat`      | [L2][T-2][TH-1]   | J/kg/K   |
| `dynamic_viscosity`  | [L-1][M][T-1]     | Pa*s     |
| `kinematic_viscosity`| [L2][T-1]         | m^2/s    |
| `thermal_conductivity`| [L][M][T-3][TH-1]| W/m/K    |
| `molar_mass`         | [M][N-1]          | kg/mol   |

### 5.3 Compound Unit Parser

Units not in the database are parsed at runtime from their components:

```python
Q(1.5, "g/s")        # → 0.0015 kg/s  [M][T-1]
Q(10,  "cm/s")       # → 0.1 m/s      [L][T-1]
Q(5,   "cm^3")       # → 5e-6 m^3     [L3]
Q(5,   "cm**3")      # ** also accepted
Q(200, "W/m^2")      # compound parsed
Q(1,   "kg*m/s^2")   # = N
```

The parser handles: `*`, `/`, `^`, `**`, and negative exponents (e.g., `m^-1`).

### 5.4 Raw Dimension Strings

```python
# Both notations produce identical Dim objects
Q(1, "[L][M][T-2]")   # standard — one bracket per dimension
Q(1, "[LMT-2]")       # compact — all in one bracket
Q(1, "[L2][M][T-2]")  # with exponents
```

### 5.5 Unit Conversions

```python
Q(101325, "Pa").to("kPa")     # 101.325 kPa
Q(101325, "Pa").to("psi")     # 14.696 psi
Q(3000,   "K").to("R")        # 5400 R
Q(1000,   "N").to("lbf")      # 224.8 lbf
Q(10,     "m/s").to("cm/s")   # 1000 cm/s
Q(0.001,  "kg/s").to("g/s")   # 1 g/s
Q(1e-6,   "m^3").to("cm^3")   # 1 cm^3
```

### 5.6 Unit System (Display)

```python
anvil.set_units("SI")         # Pa, N, m/s, K (default)
anvil.set_units("Imperial")   # psi, lbf, ft/s, R
```

### 5.7 Complete Unit List

```
Length:        m, km, cm, mm, um, in, ft, mi, nmi
Mass:          kg, g, mg, lb, lbm, slug, oz, tonne
Time:          s, ms, us, min, hr
Temperature:   K, R
Amount:        mol, kmol
Current:       A, mA
Force:         N, kN, MN, lbf
Pressure:      Pa, kPa, MPa, GPa, bar, atm, psi, psia, torr
Energy:        J, kJ, MJ, cal, kcal, BTU, eV
Power:         W, kW, MW, hp
Velocity:      m/s, km/s, km/hr, ft/s, mph, kn
Acceleration:  m/s^2, ft/s^2
Area:          m^2, cm^2, mm^2, ft^2, in^2
Volume:        m^3, cm^3, L, ft^3, gal
Density:       kg/m^3, g/cm^3, lb/ft^3, slug/ft^3
Viscosity:     Pa*s, poise, m^2/s
Specific:      J/kg, kJ/kg, BTU/lb, J/kg/K, kJ/kg/K, BTU/lb/R
Thermal:       W/m/K
Molar:         kg/mol, g/mol, J/mol/K
Mass flow:     kg/s, lb/s
Other:         V, Hz, kHz, MHz, rad, deg
```

Any compound of these (e.g., `cm/s`, `g/s`, `mW/m^2`) is parsed automatically.

---

## 6. System Operations

### 6.1 `.add()` — Define Inputs

```python
sys.add("P0", 6.9e6, "Pa")                           # value + unit string
sys.add("P0", Q(6.9e6, "Pa"))                         # Quantity object
sys.add("gamma", 1.25)                                 # dimensionless
sys.add("T0", 3500, "K", desc="Chamber temp", bounds=(200, 5000))

# Keyword style (unit inferred from Quantity):
sys.add(T0=3500*K, P0=6.9*MPa, gamma=1.25)
```

### 6.2 `.set()` — Override Values

```python
sys.set(P0=8e6)                    # bare number: keeps existing unit (Pa)
sys.set(P0=Q(1000, "psi"))         # Q() overrides value AND unit
sys.set(P0=8e6, T0=3200, gamma=1.3)  # multiple at once
```

### 6.3 `.use()` — Add Physics

```python
sys.use(my_function)               # plain Python function
sys.use(my_relation)               # Relation object
sys.use(other_system)              # System — inherits its defaults
sys.use("isentropic_ratios")       # load from registry by name
sys.use(my_adapter)                # Adapter (external tool)
sys.use(fn, map={"M": "M_exit"})   # rename inputs to match workspace
```

### 6.4 `.copy()` — Safe Duplication

```python
nozzle_a = anvil.S.rocket_nozzle.copy()   # fully independent copy
nozzle_b = anvil.S.rocket_nozzle.copy()
nozzle_a.set(P0=10e6)                      # does not affect nozzle_b
```

### 6.5 `.validate()` — Pre-Solve Check

```python
warnings = sys.validate()   # raises ValidationError on missing inputs / conflicts
```

### 6.6 `.solve()` and Explicit Solver Methods

Choose the solver explicitly:

```python
# Single-pass forward propagation (acyclic systems)
result = sys.solve_forward()

# Fixed-point iteration — Gauss-Seidel (coupled / iterative systems)
result = sys.solve_gauss_seidel(
    relaxation=0.8,    # under-relaxation factor (0 < ω ≤ 1)
    max_iter=200,
    rtol=1e-8,
    monitor=True,      # prints live residual per iteration + stores history
    verbose=False,
)

# Newton-Raphson on coupled residual (strongly nonlinear systems)
result = sys.solve_newton(
    max_iter=50,
    rtol=1e-10,
    verbose=True,
)

# Auto-select (detects cycles → chooses forward or gauss_seidel)
result = sys.solve()
result = sys.solve(method="gauss_seidel", relaxation=0.7, monitor=True)
```

**Live residual monitoring:**

When `monitor=True`, residuals are printed during each iteration:

```
  iter    0  |  residual = 6.3299e-01  |  t = 0.000s
  iter    1  |  residual = 1.7423e-01  |  t = 0.001s
  ...
  converged in 10 iterations
```

Access stored history after solve:

```python
for h in sys.history():
    print(h["iteration"], h["residual"], h["wallclock"])
```

### 6.7 `.as_relation()` — Composition

Wrap a solved System as a Relation for use inside larger Systems:

```python
nozzle_rel = nozzle.as_relation(
    inputs=["P0", "T0", "gamma"],
    outputs=["thrust", "Isp"],
)
rocket.use(nozzle_rel)
```

---

## 7. Solvers

All solvers are in `anvil.solvers`. Method names are explicit — never abstracted.

### 7.1 Scalar Root: `find_root`

```python
from anvil import solvers

x = solvers.find_root(f, bracket=(1.0, 10.0), method="brent",  tol=1e-12, maxiter=100)
x = solvers.find_root(f, x0=5.0,              method="newton", tol=1e-12)
x = solvers.find_root(f, x0=5.0,              method="secant")
# method="auto": uses brent if bracket given, newton if x0 given
```

### 7.2 Nonlinear System: `solve_nonlinear`

```python
x = solvers.solve_nonlinear(F, x0,
    method="hybr",     # Powell hybrid (default) — robust general purpose
    # method="lm"      # Levenberg-Marquardt — overdetermined systems
    # method="broyden1"# Broyden — large sparse systems
    tol=1e-10, maxiter=200, jac=None)
```

### 7.3 ODE (Explicit): `solve_ode`

For non-stiff problems — atmospheric entry, orbital mechanics, decay chains.

```python
r = solvers.solve_ode(f, t_span=(t0, tf), y0=[1.0, 0.0],
    method="RK45",    # Runge-Kutta 4/5 (default) — general non-stiff
    # method="RK23"   # Runge-Kutta 2/3 — lower accuracy, faster
    # method="DOP853" # Dormand-Prince 8/5/3 — high accuracy
    t_eval=np.linspace(t0, tf, 500),
    rtol=1e-8, atol=1e-10,
    max_step=np.inf,
    events=None,
    verbose=True)

r["t"]    # time array
r["y"]    # solution array, shape (n_states, n_points)
r["sol"]  # dense output: r["sol"](t) → y(t)
r["nfev"] # function evaluations
```

### 7.4 ODE (Stiff): `solve_ode_stiff`

For combustion kinetics, stiff chemical networks, diffusion-reaction.

```python
r = solvers.solve_ode_stiff(f, t_span, y0,
    method="BDF",     # Backward Differentiation Formula (default) — large stiff systems
    # method="Radau"  # Implicit Runge-Kutta — small stiff, higher accuracy
    jac=None,         # optional Jacobian df/dy; estimated by FD if None
    rtol=1e-6, atol=1e-10,
    events=None,
    verbose=True)
```

### 7.5 BVP: `solve_bvp`

```python
# Solve: dy/dx = f(x, y),  bc(y(a), y(b)) = 0
r = solvers.solve_bvp(func, bc,
    x=np.linspace(0, np.pi, 5),
    y_init=y0,                   # shape (n_states, len(x))
    tol=1e-3, max_nodes=1000, verbose=False)

r["x"], r["y"], r["sol"]         # sol(x) → y(x)  [callable]
```

### 7.6 PDE (1D Heat / Diffusion): `solve_pde_heat_1d`

Crank-Nicolson scheme — unconditionally stable, 2nd-order accurate.

```python
# ∂u/∂t = α ∂²u/∂x² + f(x, t, u)
r = solvers.solve_pde_heat_1d(
    alpha=1e-5,                               # diffusivity [m²/s]
    x_span=(0, 1), t_span=(0, 10),
    u_init=lambda x: np.exp(-100*(x-0.5)**2), # callable or array
    bc_left=0.0, bc_right=0.0,               # Dirichlet; None → zero-flux Neumann
    source=lambda x, t, u: np.zeros_like(x), # source term (optional)
    nx=100, nt=None,                          # nt auto-chosen if None
    verbose=True)

r["x"]   # spatial grid (nx,)
r["t"]   # time array  (nt+1,)
r["u"]   # solution    (nt+1, nx)
```

### 7.7 Optimization: `minimize`

```python
r = solvers.minimize(f, x0,
    method="L-BFGS-B",     # gradient-based + box bounds (default)
    # method="SLSQP"        # constrained (equality + inequality)
    # method="Nelder-Mead"  # gradient-free
    bounds=[(0, None), (0, 10)],
    tol=1e-8, maxiter=500, jac=None)

r["x"], r["fun"], r["success"], r["nit"]
```

---

## 8. Parametric Sweep & Sensitivity

### 8.1 Parametric Sweep

```python
import numpy as np

sweep = sys.sweep("P0", np.linspace(5e6, 30e6, 20))

# Parallel execution — uses ThreadPoolExecutor
# Best for scipy/numpy-heavy relations (GIL released during computation)
sweep = sys.sweep("P0", values, parallel=4)

# Skip failed points instead of raising
sweep = sys.sweep("P0", values, skip_errors=True)

# Pass solver options through
sweep = sys.sweep("P0", values, method="gauss_seidel", relaxation=0.7)
```

Access results:

```python
sweep.summary(outputs=["thrust", "Isp", "mdot"])
thrust_arr = sweep["thrust"]   # numpy array, SI values
p0_arr     = sweep["P0"]       # parameter array

sweep.to_csv("sweep.csv")
sweep.to_json("sweep.json")
d = sweep.to_dict(si=True)     # dict of numpy arrays
```

### 8.2 Sensitivity Analysis

Central finite difference, normalized: 1.0 means 1% input change → 1% output change.

```python
sens = sys.sensitivity(outputs=["thrust", "Isp"], step=0.01)
sens.summary()                  # ranked bar chart in terminal
top5 = sens.top("Isp", n=5)    # [(input_name, sensitivity), ...]
d = sens.to_dict()              # {output: {input: value}}
```

---

## 9. RSQ Registry

The RSQ registry is a SQLite database at `~/.anvil/registry.db`. It is seeded automatically on first import with all built-in RSQs.

### 9.1 Exploring

```python
anvil.registry.list()                      # all RSQs
anvil.registry.list(domain="aero")         # filter by domain
anvil.registry.list(type="R")              # only Relations
anvil.registry.list(tag="combustion")      # filter by tag
anvil.registry.search("shock")             # fuzzy search
anvil.registry.info("isentropic_ratios")   # metadata + inputs/outputs
anvil.registry.export("ideal_gas_density") # print source code
```

### 9.2 Using

```python
# Direct call (returns dict of values)
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)

# Load a pre-built System
nozzle = anvil.S.rocket_nozzle.copy()

# In a System
sys.use("isentropic_ratios")
sys.use("isentropic_ratios", map={"M": "M_exit"})

# One-shot solve without building a System
result = anvil.solve(ideal_gas, T=300*K, P=101325*Pa, R_gas=287*J/kg/K)
```

### 9.3 Registering

```python
# Push a function
anvil.push(my_func,
    name="my_rsq",               # optional; defaults to function name
    domain="structures",
    description="Euler-Bernoulli beam deflection",
    tags=["beam", "bending"],
    version="1.0.0")

# Update existing (merge — only fields you pass change)
anvil.update(improved_func, name="my_rsq", version="1.1.0")

# Remove
anvil.registry.remove("my_rsq")
```

**Duplicate registration warning:** pushing an RSQ name that already exists in the local registry raises a `UserWarning`. Use `anvil.update()` to signal intentional overwrite without the warning.

### 9.4 Inspection

```python
anvil.check("rocket_nozzle")            # full dependency tree + test run
report = anvil.check("rocket_nozzle", verbose=False)
report["ok"], report["inputs"], report["outputs"], report["issues"]
```

---

## 10. Built-in RSQs — Full List

55 RSQs across 10 domains. Auto-seeded on first import.

### Constants (`const`) — Quantities

| Name | Value | Unit |
|------|-------|------|
| `g0` | 9.80665 | m/s² |
| `R_universal` | 8.314462 | J/mol/K |
| `atm_pressure` | 101325 | Pa |
| `sigma_sb` | 5.670374×10⁻⁸ | W/m²K⁴ |

### Aerodynamics (`aero`, `aero.atmosphere`, `aero.compressible`, `aero.performance`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `isa_atmosphere` | h [m] | T_atm, P_atm, rho_atm, a_atm, mu_atm, sigma |
| `isentropic_ratios` | M, gamma=1.4 | T0_T, P0_P, rho0_rho |
| `area_mach_supersonic` | area_ratio, gamma | M_exit |
| `area_mach_subsonic` | area_ratio, gamma | M_sub |
| `normal_shock` | M1, gamma=1.4 | M2, P2_P1, T2_T1, rho2_rho1, P02_P01 |
| `prandtl_meyer` | M, gamma=1.4 | nu [rad], nu_deg |
| `dynamic_pressure` | rho, V | q_inf [Pa] |
| `lift_force` | rho, V, S_ref, CL | lift [N] |
| `drag_force` | rho, V, S_ref, CD | drag [N] |
| `thin_airfoil_cl` | alpha_deg, alpha_L0_deg=0, M=0 | CL, CL_alpha |
| `induced_drag` | CL, AR, e=0.85 | CDi |
| `drag_polar` | CL, CD0, AR, e=0.85 | CD, CDi, LoD |
| `oswald_efficiency` | AR, sweep_deg=0, taper=1 | e_oswald |
| `stall_speed` | W [N], rho, S_ref, CLmax | V_stall [m/s] |
| `range_breguet` | V [m/s], TSFC [1/s], LoD, W_initial, W_final | range [m], range_km |

### Propulsion (`propulsion`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `nozzle_area_ratio` | A_exit, A_throat | area_ratio |
| `exit_conditions` | T0, P0, T0_T, P0_P, gamma, R_gas | T_exit, P_exit, a_exit |
| `exit_velocity` | M_exit, a_exit | V_exit |
| `choked_mass_flow` | P0, A_throat, gamma, R_gas, T0 | mdot [kg/s] |
| `rocket_thrust` | mdot, V_exit, P_exit, P_amb, A_exit | thrust [N] |
| `specific_impulse` | thrust, mdot | Isp [s] |
| `tsiolkovsky` | Isp, mass_ratio | delta_v [m/s] |
| `rocket_nozzle` ★ | P0, T0, gamma, R_gas, A_throat, A_exit, P_amb | M_exit, thrust, Isp, mdot, … |

★ System — use `anvil.S.rocket_nozzle.copy()`

### Thermodynamics (`thermo`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `ideal_gas_density` | P, R_gas, T | rho [kg/m³] |
| `speed_of_sound` | gamma, R_gas, T | a [m/s] |
| `sutherland_viscosity` | T, T_ref=288.15, mu_ref=1.789e-5, S=110.4 | mu [Pa·s] |
| `reynolds_number` | rho, V, L_char, mu | Re |

### Heat Transfer (`heat_transfer`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `conduction_1d` | k, A_cross, dT, L_thickness | Q_cond [W] |
| `convection` | h_conv, A_surf, T_surf, T_inf | Q_conv [W] |
| `radiation` | emissivity, A_surf, T_hot, T_cold | Q_rad [W] |
| `thermal_resistance_wall` | L_thickness, k, A_cross | R_thermal |
| `fin_efficiency_rect` | h_conv, k_fin, t_fin, L_fin | eta_fin, mL |

### Structures (`structures`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `hooke_stress` | E, strain | stress [Pa] |
| `axial_stress` | F_axial, A_cross | sigma_axial [Pa] |
| `beam_deflection_cantilever` | F_tip, L_beam, E, I_moment | deflection [m], max_moment [N·m] |
| `beam_deflection_simply_supported` | w_load, L_beam, E, I_moment | deflection [m], max_moment [N·m] |
| `buckling_euler` | E, I_moment, L_eff | P_critical [N] |
| `thin_wall_hoop_stress` | P_internal, r_inner, t_wall | sigma_hoop, sigma_axial [Pa] |

### Controls (`controls`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `pid_output` | error, integral_error, derivative_error, Kp, Ki, Kd | u_pid |
| `ziegler_nichols_pid` | Ku, Tu, method="classic" | Kp, Ki, Kd, Ti, Td |
| `first_order_step` | K, tau, t_settle_criterion=0.02 | t_settle, t_rise, bandwidth_Hz |
| `second_order_metrics` | omega_n, zeta | overshoot_pct, t_peak, t_settle, t_rise, omega_d |
| `routh_hurwitz_2nd` | a1, a0 | stable |

### Materials (`materials`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `safety_factor` | allowable_stress, applied_stress | safety_factor, margin_of_safety, pass |
| `thermal_expansion_stress` | E, alpha_thermal, dT | sigma_thermal [Pa] |
| `fatigue_life_basquin` | sigma_a, sigma_f_prime, b_exponent | N_cycles |
| `miners_rule` | cycle_counts, cycle_limits | damage_index, failed, remaining_life_fraction |
| `fracture_toughness_check` | sigma, a_crack, KIc, F_geometry=1.12 | KI, safety_factor, failed |
| `composite_laminate_stiffness` | Ef, Em, Gf, Gm, nu_f, nu_m, Vf | E1, E2, G12, nu12 |

### Orbital Mechanics (`orbital`)

| Name | Inputs | Outputs |
|------|--------|---------|
| `vis_viva` | mu, r, a | V_orbital [m/s] |
| `hohmann_transfer` | mu, r1, r2 | dv1, dv2, dv_total [m/s], tof [s] |
| `orbital_period` | mu, a | T_orbital [s] |

---

## 11. Adapter Layer

Adapters wrap external tools (Python libraries, CLI programs) so they behave exactly like Relations inside a System. See `docs/ADAPTER_GUIDE.md` for the full walkthrough.

### Python Backend

```python
from anvil import Adapter, Q

def _cantera_wrapper(fuel, oxidizer, OF, Pc):
    import cantera as ct
    # ... equilibrate gas, extract properties ...
    return {"Tc": Q(gas.T, "K"), "gamma_c": gas.cp / gas.cv}

cea = Adapter("cantera_cea",
    backend="python",
    call=_cantera_wrapper,
    inputs={
        "fuel":     {"desc": "Fuel species (H2, CH4, ...)", "default": "H2"},
        "oxidizer": {"desc": "Oxidizer",                    "default": "O2"},
        "OF":       {"desc": "O/F mass ratio",              "default": 6.0},
        "Pc":       {"unit": "Pa", "desc": "Chamber pressure", "default": 10e6},
    },
    outputs={
        "Tc":      {"unit": "K",   "desc": "Chamber temperature"},
        "gamma_c": {               "desc": "Product gamma"},
    },
    tags=["combustion", "cantera"],
)

engine.use(cea)   # plugs in like any other relation
```

### CLI Backend

```python
cfd = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD flow.cfg",
    inputs={"mach": {}, "alpha_deg": {}, "Re": {}},
    outputs={"CL": {}, "CD": {}, "CM": {}},
    setup=write_config_fn,    # function(inputs_dict, workdir)
    parse=read_results_fn,    # function(workdir) -> dict
    timeout=300, cwd="./runs",
)
```

### Built-in Cantera Adapters

Located at `adapters/cantera_thermo.py`:

```python
import sys; sys.path.insert(0, "adapters")
from cantera_thermo import cea_rocket, equilibrium_flame

# cea_rocket: H2/CH4/C3H8/C2H5OH + O2 equilibrium
# Outputs: Tc, gamma_c, R_gas_c, MW_c, rho_c, cstar
cea_rocket.register()      # push to global registry

# equilibrium_flame: adiabatic flame temperature
# Outputs: T_ad, gamma, MW, rho
```

---

## 12. Project Registry

An isolated RSQ workspace per project. Prevents polluting the global registry while iterating on new relations.

```python
# Create / open a project
proj = anvil.project("my_study", path="./work")
# Creates: ./work/.anvil/project_my_study.db

# Register to project
proj.push(my_func, domain="hx", description="Draft NTU correlation")

# Access project RSQs
result = proj.R.my_func(T_in=300, mdot=2.0)
sys.use(proj.R.my_func)

# List and search
proj.list()
proj.search("NTU")
proj.remove("old_draft")

# Promote to global registry when ready
proj.promote("my_func")
proj.promote_all(overwrite=False)
```

**Context manager** — routes `anvil.push()` calls to the project automatically:

```python
with anvil.project("my_study", path="./work") as proj:
    @anvil.relation(domain="test", register=False)
    def draft_relation(UA, C_min):
        return {"NTU": UA / C_min}
    proj.push(draft_relation)      # goes to project, not global

    anvil.R.isentropic_ratios(M=2) # global RSQs still accessible

# Outside with block — promote when satisfied
proj.promote("draft_relation")
```

---

## 13. Visualization

Requires `pip install matplotlib`.

```python
from anvil import viz

# After solving with monitor=True
result = sys.solve_gauss_seidel(monitor=True)

viz.convergence(sys)                          # residual vs iteration
viz.variable_trace(sys, ["T_hot", "T_cold"])  # variable history
viz.sweep_plot(sweep, y=["thrust", "Isp"])    # sweep results grid
viz.dependency_graph(sys)                     # input→relation→output graph

# Save instead of showing
viz.sweep_plot(sweep, show=False, save="sweep.png")
```

**Jupyter / notebook display:** In Jupyter cells, result objects automatically render as HTML tables:

```python
result    # → colored input/output table
sweep     # → sweep table with units row
sens      # → sensitivity bar chart
Q(340, "m/s")  # → styled value badge
```

---

## 14. Result Objects

### `Result` — from `sys.solve()`

```python
r = sys.solve_forward()

r["thrust"]                # Quantity
r["thrust"].value          # float in display unit
r["thrust"].si             # float in SI
r["thrust"].to("kN")       # convert — returns new Quantity
r["thrust"].to("lbf").value

r.summary()                # formatted table (inputs separated from outputs)
r.to_dict()                # plain dict of display values
r.to_dict(si=True)         # plain dict of SI floats
r.to_csv("out.csv")        # variable, value, unit CSV
r.to_json("out.json")      # JSON with value + unit per key
r.keys()                   # all output names
```

### `SweepResult` — from `sys.sweep()`

```python
sw = sys.sweep("P0", values)

sw["thrust"]               # numpy array, SI values
sw["P0"]                   # parameter array
sw.summary(outputs=[...])  # formatted table
sw.to_dict(si=True)        # dict of numpy arrays
sw.to_csv("sweep.csv")
sw.to_json("sweep.json")
```

### `SensitivityResult` — from `sys.sensitivity()`

```python
sens = sys.sensitivity()

sens["Isp"]                # dict: {input_name: sensitivity_value}
sens.top("Isp", n=5)       # list of (name, value) sorted by |sensitivity|
sens.summary()             # bar chart in terminal
sens.to_dict()             # raw dict
```

---

## 15. API Reference Summary

### Top-level

```
anvil.system(name)              Create a System
anvil.relation(...)             Decorator to define + register a Relation
anvil.solve(func, **inputs)     One-shot solve without System object
anvil.R.<name>(...)             Call a built-in Relation
anvil.S.<name>                  Access a built-in System
anvil.push(obj, ...)            Register an RSQ locally
anvil.update(obj, ...)          Update an existing RSQ
anvil.search(keyword)           Search across RSQs, constants, fluids
anvil.check(name)               Full inspection + dependency tree
anvil.set_units("SI")           Set display unit system
anvil.project(name, path)       Open a project-local registry
```

### Quantity

```
Q(value, unit)                  Create
q.value / q.si / q.unit         Access
q.to(unit)                      Convert (returns new Q)
q.dim / q.dimensionless         Dimensions
```

### System

```
s = anvil.system(name)
s.add(name, value, unit)        Add input quantity
s.add(**{name: qty})            Keyword style
s.set(**overrides)              Override values
s.use(func_or_name, map={})     Add computation
s.copy()                        Deep copy
s.validate()                    Pre-solve check
s.solve_forward()               Explicit forward pass
s.solve_gauss_seidel(...)       Explicit Gauss-Seidel
s.solve_newton(...)             Explicit Newton-Raphson
s.solve(method=..., ...)        General (auto or explicit method)
s.sweep(param, values, ...)     Parametric sweep
s.sensitivity(outputs, step)    Sensitivity analysis
s.as_relation(inputs, outputs)  Wrap as Relation
s.history()                     Convergence history (monitor=True)
s.info()                        String summary of system
```

### Solvers (`anvil.solvers`)

```
find_root(f, bracket, method="brent")
find_root(f, x0, method="newton")
solve_nonlinear(F, x0, method="hybr")
solve_ode(f, t_span, y0, method="RK45")
solve_ode_stiff(f, t_span, y0, method="BDF")
solve_bvp(f, bc, x, y_init)
solve_pde_heat_1d(alpha, x_span, t_span, u_init, ...)
minimize(f, x0, method="L-BFGS-B", bounds)
```

### Registry

```
anvil.registry.list(domain, type, tag)
anvil.registry.search(keyword)
anvil.registry.info(name)
anvil.registry.export(name)
anvil.registry.remove(name)
```

### Project Registry

```
proj = anvil.project(name, path)
proj.push(obj, domain, ...)
proj.R.<name>(...)
proj.list()
proj.search(keyword)
proj.remove(name)
proj.promote(name, overwrite=False)
proj.promote_all()
```

### Visualization (`anvil.viz`)

```
viz.convergence(system, ax, show)
viz.variable_trace(system, variables, ax, show)
viz.sweep_plot(sweep_result, y, ax, show, save)
viz.dependency_graph(system, show, save)
```

### Adapter

```
Adapter(name, backend="python", call, inputs, outputs, desc, tags)
Adapter(name, backend="cli", command, setup, parse, timeout, cwd)
adapter(**inputs)               Direct call
system.use(adapter)             Use in System
anvil.push(adapter, domain)     Register in registry
```

---

## 16. Examples

All examples are in `examples/`. Run from the repo root:

```bash
python examples/ex01_rocket_nozzle.py
```

| File | Domain | Features Demonstrated |
|------|--------|-----------------------|
| `ex01_rocket_nozzle.py` | Propulsion | Registry, set, sweep, unit conversions |
| `ex02_heat_exchanger.py` | Thermal | `solve_gauss_seidel()`, monitoring, diagnostics |
| `ex03_orbital_transfer.py` | Orbital | Hohmann transfer, Tsiolkovsky, composition |
| `ex04_beam_analysis.py` | Structures | Beams, buckling, pressure vessels |
| `ex05_wind_tunnel.py` | Aero | Multi-RSQ composition, name mapping |
| `ex06_two_stage_rocket.py` | Propulsion | System composition, staging optimization |
| `ex07_combustion.py` | Combustion | Python adapter, sensitivity, export |
| `ex08_research_workflow.py` | Multi-domain | DB lookup, coupled system, material comparison |
| `ex09_cantera_cea.py` | Combustion | Cantera adapter, propellant comparison |
| `ex10_detonation.py` | Combustion | NASA CEA adapter, CJ detonation, sub-system composition |
| `ex11_ode_solvers.py` | Multi-domain | `solve_ode`, `solve_ode_stiff`, `solve_bvp`, `solve_pde_heat_1d` |
| `ex12_project_registry.py` | Workflow | `anvil.project()`, context manager, `promote()` |
| `ex13_controls_analysis.py` | Controls | PID, Z-N tuning, 2nd-order step response, stability |
| `ex14_materials_fatigue.py` | Materials | Basquin fatigue, Miner's rule, fracture, composites |
| `ex15_aero_performance.py` | Aero | ISA atmosphere, drag polar, stall speed, Breguet range |
| `ex16_jupyter_display.ipynb` | Notebook | HTML rich display — Q, Result, SweepResult, SensitivityResult |
