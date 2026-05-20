# Anvil Framework — Complete Reference Wiki

**Version 1.1.0** | Python 3.10+ | [GitHub](https://github.com/c-rk/the-anvil-framework)

---

Anvil is an engineering computation framework: write physics as plain Python functions, wire them into solvable systems, and get results with automatic unit tracking.

**Three primitives:**
- **`Q` (Quantity)** — a number + physical dimension. Arithmetic propagates units automatically.
- **`Relation`** — a computation block: keyword inputs → dict of outputs.
- **`System`** — a solvable graph of Quantities and Relations with built-in solvers, sweep, and sensitivity.

---

## Navigation

| Page | What it covers |
|------|---------------|
| [Quick Start](01_quickstart.md) | Installation, first examples, outputs |
| [Quantity](02_quantity.md) | `Q`, `Dim`, `UnitStub`, arithmetic, conversions — complete API |
| [Unit Engine](03_units.md) | All 80+ units, compound parsing, categories, custom dims |
| [Relation](04_relation.md) | `Relation`, `@anvil.relation`, `Relation.block`, input/output detection |
| [System](05_system.md) | `add`, `set`, `use`, `solve`, `sweep`, `sensitivity`, `optimize`, `as_relation` — full API |
| [Solvers](06_solvers.md) | `find_root`, `solve_nonlinear`, `solve_ode`, `solve_ode_stiff`, `solve_bvp`, `solve_pde_heat_1d`, `minimize`, `minimize_global` |
| [Registry](07_registry.md) | SQLite store, `push`, `update`, `search`, `list`, `info`, `export`, `remove`, `check` |
| [Project Registry](08_project.md) | `anvil.project()`, isolated stores, context manager, `promote` |
| [Built-in RSQs](09_builtin_rsqs.md) | All 87 RSQs — signatures, domains, example outputs (includes `misc` domain: pod_analysis, dmd_analysis, abel_inverse, abel_forward, fft_spectrum, welch_psd, stft_spectrogram, bandpass_filter, envelope_detection, cross_correlation, signal_statistics) |
| [Adapters](10_adapters.md) | `Adapter`, python/CLI backends, unit handling |
| [Sweep & Sensitivity](11_sweep_sensitivity.md) | `sys.sweep()`, `sys.sensitivity()`, result objects, parallel |
| [Visualization](12_visualization.md) | `viz.convergence`, `viz.sweep_plot`, `viz.variable_trace`, `viz.dependency_graph`, `viz.pod_energy`, `viz.dmd_spectrum` |
| [Databases](13_databases.md) | `fluids`, `materials`, `const` — built-in property tables |
| [Limits & Gotchas](14_limits.md) | What fails, edge cases, accuracy, known issues |
| [Advanced](15_advanced.md) | Composition, cycles, block relations, CFD module, Watchdog |
| [Decomposition](16_decomp.md) | `anvil.decomp` — POD, DMD, Hankel embedding, signal analysis |
| [Abel Transform](17_abel.md) | `abel_forward`, `abel_three_point`, `abel_onion`, `abel_image`, `abel_center` |
| [Signal Processing](19_signal_processing.md) | `fft_spectrum`, `welch_psd`, `stft_spectrogram`, `bandpass_filter`, `envelope_detection`, `cross_correlation`, `signal_statistics` |

---

## At a Glance

```python
import anvil
from anvil import Q, K, Pa, m, s, kg, N, J, W, kPa, MPa

# ── Quantities with units ──────────────────────────────────────
T   = 300 * K           # Q(300, "K")
P   = 6.9 * MPa         # Q(6900000, "Pa")
rho = 1.225 * kg/m**3   # Q(1.225, "kg/m^3")

# ── Unit arithmetic ───────────────────────────────────────────
F   = Q(100, "N")
A   = Q(0.01, "m^2")
sig = F / A             # → Q(10000, "Pa") — dim auto-detected
KE  = 0.5 * Q(10,"kg") * Q(30,"m/s")**2  # → Q(4500, "J")

# ── Unit conversions ──────────────────────────────────────────
P.to("psi")             # Q(1000.7, "psi")
Q(300, "K").to("R")     # Q(540, "R")

# ── Call a built-in RSQ directly ─────────────────────────────
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
# → {"T0_T": 1.8, "P0_P": 7.824, "rho0_rho": 4.347}

# ── Load a pre-built System ───────────────────────────────────
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=10e6, T0=3500)
result = nozzle.solve_forward()
result.summary()

# ── Build your own System ─────────────────────────────────────
sys = anvil.system("rayleigh_duct")
sys.add("M1",     0.3)
sys.add("T01",    400.0,  "K")
sys.add("P1",     200e3,  "Pa")
sys.add("q_heat", 300e3,  "J/kg")
sys.add("cp",     1005.0, "J/kg/K")
sys.use(my_relation)
result = sys.solve_forward()

# ── Parametric sweep ──────────────────────────────────────────
import numpy as np
sweep = sys.sweep("q_heat", np.linspace(0, 500e3, 50))
sweep.summary(outputs=["M2", "T02", "P02_P01"])

# ── Register your own RSQ ─────────────────────────────────────
proj = anvil.project("my_study", path="./work")
proj.push(my_func, domain="aero", tags=["compressible"])
proj.R.my_func(M=2.0)
proj.promote("my_func")   # → global registry
```

---

## Package Layout

```
src/anvil/
├── __init__.py          top-level API: system(), relation(), push(), solve(), R, S, QDB
├── quantity.py          Quantity (Q), Dim arithmetic
├── units.py             UnitDB, UnitStub, all unit definitions
├── relation.py          Relation class, Relation.block()
├── system.py            System, Result, SweepResult, SensitivityResult, OptimizeResult
├── solvers/
│   └── __init__.py      find_root, solve_nonlinear, solve_ode, solve_ode_stiff,
│                        solve_bvp, solve_pde_heat_1d, minimize, minimize_global
├── decomp.py            POD, DMD, hankel, pod_reconstruct, dmd_reconstruct, pod_rank
├── registry/
│   ├── __init__.py      push, search, list, info, export, remove
│   ├── store.py         SQLite backend (Store class)
│   ├── namespace.py     R., S., QDB. dot-access namespaces
│   └── loader.py        RSQ source → live object
├── seed.py              87 built-in RSQs seeded on first import
├── project.py           Project class (isolated registry)
├── adapter.py           Adapter class (python + cli backends)
├── viz.py               convergence, sweep_plot, variable_trace, dependency_graph,
│                        pod_energy, dmd_spectrum
├── inspect.py           anvil.check()
├── watchdog.py          Watchdog convergence tracker
├── db/
│   ├── __init__.py      const, fluids, materials
│   └── properties.py    FluidDB, MaterialDB data tables
├── help_.py             anvil.lookup() — in-REPL help
└── cfd/                 CFD solver (mesh, BCs, flux, viz)
```

---

## Version History (relevant to this wiki)

| Version | Key additions |
|---------|--------------|
| 1.3.0   | Current. pip-installable, adapters in `anvil.adapters`, poliastro/pykep adapters, angle Q(deg) inputs fixed in all RSQs, `Wh`/`kWh` energy units, `degC`/`degF` offset temperature units, beam RSQ unit bug fixed, auto-update seed on source change, +4 RSQs in `misc` domain (pod_analysis, dmd_analysis, abel_inverse, abel_forward), +7 signal processing RSQs (fft_spectrum, welch_psd, stft_spectrogram, bandpass_filter, envelope_detection, cross_correlation, signal_statistics), 7 new engineering adapters (XFOIL, OpenFOAM, SU2, OpenMDAO, FEniCSx, pyNASTRAN, surrogate models), total 87 RSQs, full 2D Euler CFD docs |
| 1.2.1   | +19 RSQs: orbital extended, attitude/ADCS, mission budgets, controls extended. Total 76. |
| 1.2.0   | `minimize_global` (DE/DA/SHGO/BH), `System.optimize()`, `OptimizeResult`, `anvil.decomp` (POD/DMD), `viz.pod_energy`, `viz.dmd_spectrum` |
| 1.1.0   | CFD module, Watchdog, help_ |
| 1.0.0   | Project registry, Jupyter display, parallel sweep, 57 RSQs |
| 0.x     | Core Q/Relation/System, basic registry |

---

## Dependencies

| Package | Required | Purpose |
|---------|----------|---------|
| numpy | Yes | Array math |
| scipy | Yes | All 7 solvers |
| matplotlib | Optional | `viz.*` functions |
| cantera | Optional | Combustion adapters |
| jupyter | Optional | `_repr_html_` display |
