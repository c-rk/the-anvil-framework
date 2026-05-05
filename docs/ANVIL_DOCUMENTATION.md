# Anvil Framework Documentation

**Version 0.4.0** | From equations to engineering tools

---

## Table of Contents

1. Overview
2. Installation
3. Quick Start
4. Core Primitives (Quantity, Relation, System)
5. Unit Engine (categories, conversions, custom units, full unit list)
6. System Operations (add, set, use, copy, solve, sweep, name mapping, composition)
7. Solvers
8. Adapter Layer
9. RSQ Registry (built-in RSQs, commands, publishing)
10. Built-in Constants
11. Result Objects
12. API Reference Summary

---

## 1. Overview

Anvil is a computation framework for engineering and scientific research. You write physics as plain Python functions, wire them into solvable systems, and get results with proper units -- automatically.

The framework is built on three primitives:

- **Q (Quantity)** -- a number with physical dimensions and units
- **R (Relation)** -- a computation: inputs go in, outputs come out
- **S (System)** -- a graph of Quantities and Relations that can be solved

A solved System can become a Relation in a larger System. This recursive composition lets you build complex multi-physics tools from simple, testable building blocks.

**Dependencies:** Python 3.10+, NumPy, SciPy. Nothing else.

---

## 2. Installation

```bash
# From the source directory
cd anvil-03-1
pip install -e .

# Or just add src/ to your path
import sys
sys.path.insert(0, "path/to/anvil-03-1/src")
import anvil
```

---

## 3. Quick Start

```python
import anvil
from anvil import Q, System

# 1. Use a pre-built Relation from the registry
result = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
print(result)  # {'T0_T': 1.8, 'P0_P': 7.824, 'rho0_rho': 4.347}

# 2. Load a pre-built System, override defaults, solve
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=10e6, T0=3200)
nozzle.solve().summary()

# 3. Build your own System from scratch
sys = System("my_calc")
sys.add("rho", 1.225, "kg/m^3")
sys.add("V", 100, "m/s")

def dynamic_pressure(rho, V):
    return {"q": Q(0.5 * rho * V**2, "Pa")}

sys.use(dynamic_pressure)
sys.solve().summary()
```

---

## 4. Core Primitives

### 4.1 Quantity (Q)

A numerical value with physical dimensions. Internally stored in SI base units.

```python
from anvil import Q

# Create with a specific unit
p = Q(101325, "Pa")
v = Q(100, "m/s")

# Create with a dimension category
p = Q(101325, "pressure")        # resolves to Pa in SI

# Create with raw dimension expression
p = Q(101325, "[L-1][M][T-2]")   # same as Pa

# Dimensionless
gamma = Q(1.4)
```

**Arithmetic propagates dimensions automatically:**

```python
rho = Q(1.225, "kg/m^3")
v   = Q(100, "m/s")
q   = 0.5 * rho * v**2      # result: 6125.0 Pa (auto-detected)

F   = Q(10, "kg") * Q(9.81, "m/s^2")   # 98.1 N
E   = Q(100, "N") * Q(5, "m")           # 500 J
P   = Q(1000, "J") / Q(2, "s")          # 500 W
```

**Properties:** q.value (display value), q.si (SI value), q.unit (unit string), q.dim (Dim object), q.dimensionless (bool)

**Methods:** q.to("kPa") (convert), q.in_bounds() (check bounds)


### 4.2 Relation (R)

A computation block. Write a plain Python function that returns a dict.

```python
def isentropic_ratios(M, gamma=1.4):
    T_ratio = 1 + ((gamma - 1) / 2) * M**2
    P_ratio = T_ratio ** (gamma / (gamma - 1))
    return {"T_ratio": T_ratio, "P_ratio": P_ratio}
```

Rules: accept keyword arguments, return dict, use Q(value, "unit") for dimensional outputs.

**Relation.block()** groups multiple functions into one:

```python
physics = Relation.block("nozzle_physics",
    steps=[area_ratio_fn, mach_fn, isentropic_fn, thrust_fn],
    tags=["propulsion"],
)
system.use(physics)
```


### 4.3 System (S)

A solvable engineering problem: quantities wired to relations.

```python
nozzle = System("rocket_nozzle")
nozzle.add("P0", 6.9e6, "Pa")
nozzle.add("T0", 3500, "K")
nozzle.use(area_ratio_fn)
nozzle.use(thrust_fn)
result = nozzle.solve()
result.summary()
```

---

## 5. Unit Engine

### 5.1 How It Works

Every Quantity carries a Dim object that propagates through arithmetic:

```
Q(10, "kg") * Q(9.81, "m/s^2")
  value: 10 * 9.81 = 98.1
  dim:   [M] * [L][T-2] = [L][M][T-2]
  lookup: [L][M][T-2] --> "N"
  result: 98.1 N
```

If no named unit exists for the result, the raw dimension is shown: [L2][M][T-2][TH-1]. The computation never fails because of a missing unit name.


### 5.2 Dimension Categories

    dimensionless         (none)          (none)
    length                [L]             m
    area                  [L2]            m^2
    volume                [L3]            m^3
    mass                  [M]             kg
    time                  [T]             s
    temperature           [TH]            K
    velocity              [L][T-1]        m/s
    acceleration          [L][T-2]        m/s^2
    force                 [L][M][T-2]     N
    pressure / stress     [L-1][M][T-2]   Pa
    energy                [L2][M][T-2]    J
    power                 [L2][M][T-3]    W
    density               [L-3][M]        kg/m^3
    frequency             [T-1]           Hz
    mass_flow             [M][T-1]        kg/s
    specific_energy       [L2][T-2]       J/kg
    specific_heat         [L2][T-2][TH-1] J/kg/K
    dynamic_viscosity     [L-1][M][T-1]   Pa*s
    kinematic_viscosity   [L2][T-1]       m^2/s
    thermal_conductivity  [L][M][T-3][TH-1] W/m/K
    molar_mass            [M][N-1]        kg/mol


### 5.3 Unit Conversions

```python
Q(101325, "Pa").to("kPa")    # 101.325 kPa
Q(101325, "Pa").to("psi")    # 14.696 psi
Q(101325, "Pa").to("atm")    # 1.0 atm
Q(3000, "K").to("R")          # 5400 R
Q(1000, "N").to("lbf")        # 224.8 lbf
```


### 5.4 Custom / Unknown Units

```python
a = Q(5, "flarps")           # auto-creates [flarps] dimension
b = a * Q(3, "s")            # 15 [flarps][T]
c = a ** 2                   # 25 [flarps2]
```


### 5.5 Unit Systems

```python
anvil.set_units("SI")        # Pa, N, m/s, K (default)
anvil.set_units("Imperial")  # psi, lbf, ft/s, R
```


### 5.6 Complete Unit List (96 units)

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

---

## 6. System Operations

### 6.1 .add() -- Define Inputs

```python
sys.add("P0", 6.9e6, "Pa")           # value + unit
sys.add("P0", Q(6.9e6, "Pa"))        # Quantity object
sys.add("gamma", 1.25)                # dimensionless
sys.add("T0", 3500, "K", desc="Chamber temperature", bounds=(200, 5000))
```

### 6.2 .set() -- Override Values

```python
sys.set(P0=8e6)                       # bare number: keeps Pa
sys.set(P0=Q(1000, "psi"))            # Q(): overrides value AND unit
sys.set(P0=8e6, T0=3200, gamma=1.3)   # multiple at once
```

### 6.3 .use() -- Add Physics

```python
sys.use(my_function)                   # plain Python function
sys.use(my_relation)                   # Relation object
sys.use(other_system)                  # System (inherits defaults)
sys.use("isentropic_ratios")          # registry lookup
sys.use(my_adapter)                    # Adapter (external tool)
```

### 6.4 .copy() -- Safe Duplication

```python
nozzle = anvil.S.rocket_nozzle.copy()  # independent copy
nozzle.set(P0=10e6)                     # doesn't affect original
```

### 6.5 .solve() -- Run the Solver

```python
result = sys.solve()                    # auto-detects solver
result = sys.solve(
    method="gauss_seidel",              # "forward", "gauss_seidel", "newton"
    max_iter=200,
    rtol=1e-8,
    relaxation=0.7,
    monitor=True,
    verbose=True,
)
```

### 6.6 .sweep() -- Parametric Studies

```python
sweep = sys.sweep("P0", np.linspace(1e6, 20e6, 10))
sweep.summary(outputs=["thrust", "Isp"])
data = sweep.to_dict()
```

### 6.7 Name Mapping

```python
sys.use("isentropic_ratios", map={"M": "M_exit"})
```

### 6.8 Composition

```python
stage = System("rocket_stage")
stage.use(nozzle)                # inherits all nozzle defaults
stage.add("mass_ratio", 4.0)    # only add what's new
stage.use(delta_v_function)
stage.solve()
```

---

## 7. Solvers

### 7.1 System Solvers

    "forward"       Auto for acyclic. Single pass through dependency order.
    "gauss_seidel"  Auto for coupled. Fixed-point iteration with under-relaxation.
    "newton"        For tight coupling. Newton-Raphson on coupled residual.

### 7.2 Standalone Functions

```python
from anvil import solvers

# Scalar root: f(x) = 0
solvers.find_root(f, bracket=(a, b))         # Brent method
solvers.find_root(f, x0=guess)               # Newton method

# Nonlinear system: F(x) = 0
solvers.solve_nonlinear(F, x0, method="hybr", tol=1e-10, maxiter=200)

# ODE: dy/dt = f(t, y)
solvers.solve_ode(f, t_span, y0, method="RK45", t_eval=..., rtol=1e-8)

# Optimization: minimize f(x)
solvers.minimize(f, x0, method="L-BFGS-B", bounds=..., tol=1e-8)
```

### 7.3 Convergence Monitoring

```python
result = sys.solve(monitor=True)
for h in sys.history():
    print(f"  iter {h['iteration']}  residual={h['residual']:.2e}")
```

---

## 8. Adapter Layer

Wrap external tools as Relations.

### Python Backend

```python
from anvil import Adapter

cea = Adapter("cea_rocket",
    backend="python",
    call=my_wrapper_function,
    inputs={"fuel": {}, "OF": {}, "Pc": {"unit": "Pa"}},
    outputs={"Tc": {"unit": "K"}, "gamma": {}, "cstar": {"unit": "m/s"}},
)
system.use(cea)  # works like any function
```

### CLI Backend

```python
cfd = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD {config_file}",
    inputs={"mach": {}, "alpha_deg": {}},
    outputs={"CL": {}, "CD": {}},
    setup=write_config,    # function(inputs, workdir)
    parse=read_results,    # function(workdir) -> dict
    timeout=300,
)
```

---

## 9. RSQ Registry

### 9.1 Built-in Relations (15)

    isentropic_ratios      aero.compressible    T0/T, P0/P, rho0/rho from Mach
    area_mach_supersonic   aero.compressible    Supersonic M from A/A*
    area_mach_subsonic     aero.compressible    Subsonic M from A/A*
    normal_shock           aero.compressible    M2, P2/P1, T2/T1, rho2/rho1, P02/P01
    prandtl_meyer          aero.compressible    Expansion angle from Mach
    dynamic_pressure       aero                 q = 0.5 * rho * V^2
    nozzle_area_ratio      propulsion           A_exit / A_throat
    exit_conditions        propulsion           T_exit, P_exit, a_exit
    exit_velocity          propulsion           V_exit = M * a
    choked_mass_flow       propulsion           Choked throat mass flow
    rocket_thrust          propulsion           F = mdot*V + (Pe-Pa)*Ae
    specific_impulse       propulsion           Isp = F / (mdot*g0)
    ideal_gas_density      thermo               rho = P / (R*T)
    speed_of_sound         thermo               a = sqrt(gamma*R*T)
    vis_viva               orbital              V = sqrt(mu*(2/r - 1/a))

### 9.2 Built-in Systems (1)

    rocket_nozzle          propulsion           Full quasi-1D nozzle (7 inputs, 8 Relations)
        Defaults: P0=6.9 MPa, T0=3500 K, gamma=1.25, R_gas=320 J/kg/K,
                  A_throat=0.01 m^2, A_exit=0.08 m^2, P_amb=101325 Pa

### 9.3 Built-in Quantities (3)

    g0              const    9.80665 m/s^2
    R_universal     const    8.314 J/mol/K
    atm_pressure    const    101325 Pa

### 9.4 Registry Commands

```python
anvil.registry.list()                    # all installed RSQs
anvil.registry.list(type="R")            # only Relations
anvil.registry.list(domain="aero")       # filter by domain
anvil.registry.search("shock")           # fuzzy search
anvil.registry.info("isentropic_ratios") # detailed metadata
anvil.registry.export("isentropic_ratios") # source code
anvil.registry.remove("old_tool")        # uninstall
```

### 9.5 Publishing

```python
anvil.push(my_function, domain="structures", tags=["beam", "bending"],
           description="Euler-Bernoulli beam deflection")
```

---

## 10. Built-in Constants

Access via `from anvil.db import const`:

    const.c         299792458       m/s         Speed of light
    const.h         6.626e-34       J           Planck constant
    const.k_B       1.381e-23       J/kg/K      Boltzmann constant
    const.R         8.314           J/mol/K     Universal gas constant
    const.N_A       6.022e23        (none)      Avogadro's number
    const.g0        9.80665         m/s^2       Standard gravity
    const.sigma     5.670e-8        W           Stefan-Boltzmann
    const.atm       101325          Pa          Standard atmosphere
    const.T_sl      288.15          K           Sea-level temperature
    const.rho_sl    1.225           kg/m^3      Sea-level density
    const.a_sl      340.294         m/s         Sea-level speed of sound
    const.gamma_air 1.4             (none)      Specific heat ratio (air)
    const.R_air     287.058         J/kg/K      Gas constant (air)
    const.M_air     0.02896         kg/mol      Molar mass (air)
    const.cp_air    1005            J/kg/K      Specific heat (air)
    const.pi        3.14159         (none)      Pi

```python
const.search("gravity")    # find by keyword
const.list()               # all names
```

---

## 11. Result Objects

### Result (from solve)

```python
r = sys.solve()
r["thrust"]                # Quantity
r["thrust"].value          # display value
r["thrust"].si             # SI float
r["thrust"].to("lbf")     # convert
r.summary()                # formatted table
r.to_dict()                # plain dict
r.to_dict(si=True)         # SI floats
```

### SweepResult (from sweep)

```python
sw = sys.sweep("P0", values)
sw["thrust"]               # numpy array
sw.summary()               # formatted table
sw.to_dict()               # dict of arrays
```

---

## 12. API Reference Summary

### Top-level

    anvil.R.<name>(...)        Call a Relation
    anvil.S.<name>             Access a System
    anvil.QDB.<name>           Access a Quantity
    anvil.fetch(names)         Load RSQs
    anvil.push(obj, ...)       Register locally
    anvil.search(keyword)      Search everything
    anvil.set_units("SI")      Set unit system

### Quantity

    Q(value, unit)             Create
    q.value / q.si / q.unit    Access
    q.to(unit)                 Convert
    q.dim / q.dimensionless    Dimensions

### System

    System(name)               Create
    .add(name, value, unit)    Add input
    .set(name=value)           Override
    .use(func_or_name)         Add computation
    .copy()                    Deep copy
    .solve(method, ...)        Solve
    .sweep(param, values)      Parametric study
    .as_relation(...)          Wrap as Relation
    .history()                 Convergence data

### Solvers

    solvers.find_root(f, ...)           Scalar root
    solvers.solve_nonlinear(F, x0)      System of equations
    solvers.solve_ode(f, t_span, y0)    ODE integration
    solvers.minimize(f, x0)             Optimization

### Adapter

    Adapter(name, backend, call, inputs, outputs)   Create
    adapter(...)                                     Call
    system.use(adapter)                              Use in System

### Inspection

    anvil.check(name)                 Full inspection + dependency tree
    anvil.check(name, verbose=False)  Returns report dict

### Monitoring

    from anvil.monitor import diagnose, plot_convergence, plot_variables, plot_sweep, plot_system

    diagnose(system)                        Pre-solve diagnostics
    plot_convergence(sys, save="...")        Residual plots
    plot_variables(sys, [...], save="...")   Variable trace
    plot_sweep(sweep, y=[...], save="...")   Sweep charts
    plot_system(sys, save="...")             Dependency graph

### See Also

    docs/ADAPTER_GUIDE.md    Detailed adapter walkthrough + AI agent prompt template
