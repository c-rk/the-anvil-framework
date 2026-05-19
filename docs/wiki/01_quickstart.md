# Quick Start

## Installation

```bash
git clone https://github.com/c-rk/the-anvil-framework
cd the-anvil-framework/anvil-03-1

# Core + visualization
pip install -e ".[viz]"

# Core + specific adapter dependencies
pip install -e ".[poliastro]"   # poliastro + astropy
pip install -e ".[pykep]"       # pykep
pip install -e ".[adapters]"    # all adapter deps

# Cantera (conda recommended)
conda install -c cantera cantera
```

After install, `import anvil` works from any directory and any script. No `sys.path` manipulation needed.

| Extra | What it enables |
|-------|----------------|
| (none) | All built-in RSQs, all solvers, registry |
| `viz` | `anvil.viz.*` plots (requires matplotlib) |
| `poliastro` | `anvil.adapters.poliastro_orbits` |
| `pykep` | `anvil.adapters.pykep_trajectories` |
| `adapters` | All adapter optional deps |
| `all` | viz + all adapters |

---

## 5-Minute Tutorial

### Step 1 — Create Quantities

```python
import anvil
from anvil import Q, K, Pa, m, s, kg, N, J, W, kPa, MPa

# Three equivalent styles
T = Q(300, "K")          # string unit
T = Q(300, "temperature") # category alias
T = 300 * K              # unit-stub syntax (cleanest)

P   = 101325 * Pa
v   = 340 * (m/s)
g   = 9.81 * m/s**2
rho = 1.225 * kg/m**3
```

### Step 2 — Arithmetic propagates units

```python
F   = Q(100, "N")
A   = Q(0.01, "m^2")
sig = F / A              # → 10000.00 Pa  (dimension auto-detected)

KE  = 0.5 * Q(10,"kg") * Q(30,"m/s")**2  # → 4500.00 J

print(sig)               # 10000.00 Pa
print(KE)                # 4500.00 J
print(KE.to("kJ"))       # 4.5000 kJ
print(KE.si)             # 4500.0  (always SI float)
```

### Step 3 — Call a built-in RSQ

```python
# Direct call — no System needed
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
print(r["T0_T"])    # 1.8
print(r["P0_P"])    # 7.8244
print(r["rho0_rho"]) # 4.3469
```

### Step 4 — Use a pre-built System

```python
nozzle = anvil.S.rocket_nozzle.copy()   # deep copy — safe to modify
nozzle.set(P0=10e6, T0=3500)            # override values, keep units

result = nozzle.solve_forward()
result.summary()
```

**Output:**
```
--------------------------------------------------------
  rocket_nozzle -- results
--------------------------------------------------------
  P0                        1.0000e+07 Pa
  T0                        3500.00 K
  gamma                     1.2500
  R_gas                     320.00 J/kg/K
  A_throat                  0.01 m^2
  A_exit                    0.08 m^2
  P_amb                     101325.00 Pa
                            ---
  area_ratio                8.0000
  M_exit                    3.6423
  T0_T                      2.6469
  P0_P                      59.6093
  rho0_rho                  22.5243
  T_exit                    1322.66 K
  P_exit                    167773.97 Pa
  a_exit                    728.41 m/s
  V_exit                    2652.17 m/s
  mdot                      12.12 kg/s
  thrust                    32143.09 N
  Isp                       270.20 s
--------------------------------------------------------
```

### Step 5 — Build your own System

```python
def lift_coeff(W, S_ref, V, rho):
    q = 0.5 * rho * V**2
    CL = W / (q * S_ref)
    return {"q_inf": Q(q, "Pa"), "CL": CL}

sys = anvil.system("wing_loading")
sys.add("W",     50000, "N")
sys.add("S_ref", 20,    "m^2")
sys.add("V",     80,    "m/s")
sys.add("rho",   1.225, "kg/m^3")
sys.use(lift_coeff)

result = sys.solve_forward()
result.summary()
# CL = 0.7994, q_inf = 3920.00 Pa
```

### Step 6 — Sweep a parameter

```python
import numpy as np

sweep = sys.sweep("V", np.linspace(50, 150, 8))
sweep.summary(outputs=["CL", "q_inf"])
```

**Output:**
```
----------------------------------------------------------------------
  wing_loading -- sweep over V
----------------------------------------------------------------------
               V            CL         q_inf
            [m/s]                      [Pa]
  ----------------------------------------------------------------------
              50        2.0388     1531.25
           64.29        1.2337     2534.06
           78.57        0.8249     3783.89
           92.86        0.5913     5280.73
             107        0.4453     7024.58
           121.4        0.3460     9015.45
           135.7        0.2773     11253.3
             150        0.2269     13781.3
----------------------------------------------------------------------
```

---

## Common Patterns

### One-shot solve (no System object)

```python
result = anvil.solve("isentropic_ratios", M=2.0, gamma=1.4)
print(result["P0_P"])   # 7.824
```

### Register and reuse a custom RSQ

```python
@anvil.relation(domain="aero", tags=["compressible"])
def dynamic_pressure(rho, V):
    return {"q_inf": Q(0.5 * rho * V**2, "Pa")}

# Now available globally
anvil.R.dynamic_pressure(rho=1.225, V=100)
# {"q_inf": 6125.00 Pa}
```

### Coupled/iterative system (Gauss-Seidel)

```python
# System with a feedback loop — use solve_gauss_seidel()
result = sys.solve_gauss_seidel(
    relaxation=0.8,
    max_iter=200,
    rtol=1e-8,
    monitor=True,       # prints live residuals
)
```

### Project registry workflow

```python
proj = anvil.project("my_study", path="./work")

proj.push(rayleigh_ratios, domain="aero.compressible")
proj.push(rayleigh_heat,   domain="aero.compressible")

result = proj.R.rayleigh_heat(M1=0.3, T01=300.0, P1=101325.0,
                               q_heat=200e3, cp=1005.0)
print(result["M2"])     # 0.428
print(result["T02"])    # 499.00 K

proj.promote("rayleigh_heat")  # → global registry
```

---

## What Anvil Is NOT

- **Not a symbolic solver** — no algebraic manipulation, no CAS. Relations must be written as explicit Python functions.
- **Not a FEA/FEM framework** — the PDE solver is limited to 1D parabolic (heat/diffusion). Complex PDEs need an external adapter.
- **Not a unit checker for general code** — units are tracked on `Q` objects only. Raw Python floats carry no dimension information.
- **Not fully DOF-aware** — `validate()` warns when a declared variable is overwritten by a relation or goes unused, but does not verify that equations equal unknowns in the general case. A fully underdetermined system (where nothing downstream needs the missing variable) still produces no error.
- **Not parallel by default** — `solve_gauss_seidel` and `solve_newton` are single-threaded. Use `sweep(parallel=N)` for concurrent parametric sweeps.
