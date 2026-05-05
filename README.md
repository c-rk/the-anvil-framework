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
nozzle.solve().summary()

# Inspect any RSQ
anvil.check("rocket_nozzle")

# Parametric sweep
sweep = nozzle.sweep("P0", [5e6, 10e6, 15e6, 20e6])
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
- **38 built-in RSQs** across 7 domains (aero, propulsion, structures, heat transfer, orbital, thermo, constants)
- **Forward, Gauss-Seidel, and Newton solvers** with convergence monitoring
- **Parametric sweeps** with formatted tables and CSV/JSON export
- **Sensitivity analysis** with normalized derivatives
- **Adapter layer** for external tools (Cantera, CoolProp, SU2, CLI programs)
- **RSQ registry** with SQLite storage, lazy namespaces, search
- **`anvil.check()`** for one-call RSQ inspection and dependency trees
- **Visualization**: convergence plots, sweep charts, dependency graphs

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

## Documentation

- `docs/ANVIL_DOCUMENTATION.md` -- Complete API reference
- `docs/ADAPTER_GUIDE.md` -- Adapter walkthrough + AI agent prompt template

## Requirements

- Python 3.10+
- NumPy >= 1.24
- SciPy >= 1.11
- matplotlib >= 3.7 (optional, for visualization)
