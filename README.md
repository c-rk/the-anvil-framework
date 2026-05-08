# Anvil Framework

**From equations to engineering tools.**

Anvil is a computation framework for engineering and scientific research. Write physics as plain Python functions, wire them into solvable systems, and get results with proper units -- automatically.

## Install

```bash
pip install -e .                # core (numpy + scipy)
pip install -e ".[viz]"         # + matplotlib for plots
pip install -e ".[all]"         # everything
```

## Quick Start

```python
import anvil
from anvil import Q, System

# Use built-in relations directly
result = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)

# Load a pre-built system, customize, solve
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=10e6, T0=3200)
nozzle.solve_forward().summary()

# Inspect any RSQ
anvil.check("rocket_nozzle")

# Parametric sweep (parallel supported)
sweep = nozzle.sweep("P0", [5e6, 10e6, 15e6, 20e6], parallel=4)
sweep.summary(outputs=["thrust", "Isp"])

# Sensitivity analysis
sens = nozzle.sensitivity(outputs=["thrust", "Isp"])
sens.summary()

# Export
result.to_csv("results.csv")
result.to_json("results.json")
```

## Features

- **Three primitives**: Q (Quantity), R (Relation), S (System)
- **96 units** with automatic dimension tracking through all arithmetic
- **55+ built-in RSQs** across 10 domains (aero, propulsion, structures, heat transfer, orbital, thermo, controls, materials, constants)
- **Explicit solvers**: `solve_forward()`, `solve_gauss_seidel()`, `solve_newton()` with convergence monitoring
- **ODE / BVP / PDE solvers**: RK45, BDF, Radau, Crank-Nicolson via `anvil.solvers`
- **Parametric sweeps** with parallel execution, formatted tables, CSV/JSON export
- **Sensitivity analysis** with normalized derivatives
- **Project registry**: isolated per-project SQLite store, promote RSQs to global when ready
- **Adapter layer** for external tools (Cantera, CoolProp, SU2, CLI programs)
- **RSQ registry** with SQLite storage, lazy namespaces, fuzzy search
- **`anvil.check()`** for one-call RSQ inspection and dependency trees
- **Visualization**: convergence plots, sweep charts, dependency graphs
- **Jupyter rich display**: HTML tables for Quantity, Result, SweepResult, SensitivityResult

## Examples

| Example | Domain | Demonstrates |
|---------|--------|-------------|
| `ex01_rocket_nozzle.py` | Propulsion | Registry, set, sweep, unit conversions |
| `ex02_heat_exchanger.py` | Thermal | Coupled solver, monitoring, diagnostics |
| `ex03_orbital_transfer.py` | Orbital | Hohmann transfer, Tsiolkovsky, composition |
| `ex04_beam_analysis.py` | Structures | Beams, buckling, pressure vessels |
| `ex05_wind_tunnel.py` | Aero | Multi-RSQ composition, name mapping |
| `ex06_two_stage_rocket.py` | Propulsion | System composition, staging optimization |
| `ex07_combustion.py` | Combustion | Adapter (Cantera-style), sensitivity, export |
| `ex08_research_workflow.py` | Multi-domain | Full workflow: DB lookup, coupled system, sweep, export |
| `ex09_cantera_cea.py` | Combustion | Cantera adapter, propellant comparison, export |
| `ex10_detonation.py` | Combustion | NASA CEA adapter, CJ detonation, system composition |
| `ex11_ode_solvers.py` | Multi-domain | ODE (RK45/BDF), BVP, 1D PDE heat equation |
| `ex12_project_registry.py` | Workflow | Project store, context manager, promote to global |
| `ex13_controls_analysis.py` | Controls | PID tuning, Z-N, 2nd-order step response, stability |
| `ex14_materials_fatigue.py` | Materials | Fatigue life, Miner's rule, fracture, composites |
| `ex15_aero_performance.py` | Aero | ISA atmosphere, drag polar, stall speed, Breguet range |
| `ex16_jupyter_display.ipynb` | Notebook | Rich HTML display for all result types |

## Documentation

- `docs/ANVIL_DOCUMENTATION.md` -- Complete API reference
- `docs/ADAPTER_GUIDE.md` -- Adapter walkthrough + AI agent prompt template
- `docs/ANVIL_GUIDE.html` -- Slide deck guide (open in browser)

## Requirements

- Python 3.10+
- NumPy >= 1.24
- SciPy >= 1.11
- matplotlib >= 3.7 (optional, for visualization)
- jupyter (optional, for notebook display)
