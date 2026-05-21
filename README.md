# Anvil Framework

**From equations to engineering tools.**

Anvil is a computation framework for engineering and scientific research. Write physics as plain Python functions, wire them into solvable systems, and get results with automatic unit tracking.

## Install

After downloading the repo, refer `ANVIL_GUIDE.html` inside /docs to get started.

```bash
pip install -e .                      # core (numpy + scipy)
pip install -e ".[viz]"               # + matplotlib
pip install -e ".[surrogate]"         # + scikit-learn (GP/poly surrogates)
pip install -e ".[nastran]"           # + pyNASTRAN (FEM post-processing)
pip install -e ".[openmdao]"          # + OpenMDAO (MDO problems)
pip install -e ".[all]"               # numpy, scipy, matplotlib, pyNASTRAN, openmdao, scikit-learn
```

XFOIL, SU2, and OpenFOAM adapters require the respective binaries on PATH — no pip package.
FEniCSx requires `conda install -c conda-forge fenics-dolfinx mpi4py`.

## Quick Start

```python
import anvil
from anvil import Q, System

# Call a built-in RSQ directly
result = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
# {'T0_T': 1.8, 'P0_P': 7.824, 'rho0_rho': 4.347}

# Load a pre-built system, customize, solve
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P0=10e6, T0=3200)
nozzle.solve_forward().summary()

# Parametric sweep (parallel supported)
import numpy as np
sweep = nozzle.sweep("P0", np.linspace(5e6, 20e6, 8), parallel=4)
sweep.summary(outputs=["thrust", "Isp"])

# Sensitivity analysis
nozzle.sensitivity(outputs=["thrust", "Isp"]).summary()

# Signal processing RSQs
t = np.linspace(0, 1, 4096, endpoint=False)
r = anvil.R.fft_spectrum(signal=np.sin(2*np.pi*50*t), dt=t[1]-t[0])
# {'dominant_freq': 50.0, 'rms': 0.707, 'thd': 0.0, ...}

# Export
result.to_csv("results.csv")
result.to_json("results.json")
```

## Features

- **Three primitives**: `Q` (Quantity with units), `Relation` (physics function), `System` (solvable graph)
- **102 units** with automatic dimension tracking through all arithmetic; offset temperature units (`degC`, `degF`)
- **87 built-in RSQs** across 12 domains: aero, propulsion, structures, heat transfer, orbital, thermo, controls, materials, mission, signal processing, decomposition, constants
- **Solvers**: `solve_forward()`, `solve_gauss_seidel()`, `solve_newton()` with convergence monitoring
- **ODE / BVP / PDE**: RK45, BDF, Radau, Crank-Nicolson, global optimizers via `anvil.solvers`
- **Parametric sweeps** with parallel execution, formatted tables, CSV/JSON export
- **Sensitivity analysis** with normalized derivatives
- **Project registry**: isolated per-project SQLite store; promote RSQs to global when ready
- **Adapter layer**: wrap any Python library or CLI tool as a native Anvil Relation
- **Signal processing RSQs**: `fft_spectrum`, `welch_psd`, `stft_spectrogram`, `bandpass_filter`, `envelope_detection`, `cross_correlation`, `signal_statistics`
- **Decomposition RSQs**: `pod_analysis`, `dmd_analysis`, `abel_inverse`, `abel_forward`
- **Engineering adapters** (all with analytical mock fallbacks):
  - Aerodynamics: XFOIL (2D airfoil polars), SU2 (Euler/RANS), OpenFOAM (simpleFoam/rhoSimpleFoam)
  - FEM: FEniCSx (linear elasticity, heat conduction), pyNASTRAN (SOL 101/103, MYSTRAN support)
  - MDO: OpenMDAO (factory wrapper + Sellar benchmark)
  - Surrogates: Gaussian Process, polynomial chaos, RBF interpolation (scikit-learn / scipy)
  - Propulsion: Cantera (equilibrium combustion), NASA CEA (detonation)
  - Orbital: poliastro (Keplerian elements, Hohmann transfers), pykep (Lambert arcs)
- **Visualization**: convergence plots, sweep charts, dependency graphs, POD energy, DMD spectrum
- **Jupyter rich display**: HTML tables for all result types

## Domains and RSQ Count

| Domain | RSQs | Example RSQs |
|--------|------|-------------|
| `aero` | 10 | `isentropic_ratios`, `normal_shock`, `oblique_shock`, `nozzle_area_ratio` |
| `propulsion` | 8 | `rocket_nozzle`, `tsiolkovsky`, `specific_impulse`, `combustion_temp` |
| `structures` | 8 | `beam_deflection`, `buckling_euler`, `pressure_vessel_hoop`, `fatigue_life_basquin` |
| `heat` | 9 | `conduction_1d`, `convection`, `fin_efficiency_rect`, `heat_exchanger_lmtd` |
| `orbital` | 12 | `hohmann_transfer`, `vis_viva`, `orbital_period`, `sphere_of_influence` |
| `thermo` | 6 | `ideal_gas_density`, `isentropic_process`, `carnot_efficiency` |
| `controls` | 8 | `pid_response`, `second_order_step`, `zn_tuning`, `lead_lag_compensator` |
| `materials` | 7 | `youngs_modulus_composite`, `thermal_expansion`, `miners_rule` |
| `mission` | 6 | `delta_v_budget`, `mass_fraction`, `payload_ratio` |
| `misc` | 11 | `pod_analysis`, `dmd_analysis`, `fft_spectrum`, `welch_psd`, `bandpass_filter`, … |
| `const` | 2 | `g0`, `R_universal` |

## Examples

| File | Domain | Demonstrates |
|------|--------|-------------|
| `ex01_rocket_nozzle.py` | Propulsion | Registry, sweep, unit conversions |
| `ex02_heat_exchanger.py` | Thermal | Coupled solver, monitoring |
| `ex03_orbital_transfer.py` | Orbital | Hohmann transfer, Tsiolkovsky |
| `ex04_beam_analysis.py` | Structures | Beams, buckling, pressure vessels |
| `ex05_wind_tunnel.py` | Aero | Multi-RSQ composition, name mapping |
| `ex06_two_stage_rocket.py` | Propulsion | System composition, staging |
| `ex07_combustion.py` | Combustion | Cantera adapter, sensitivity |
| `ex08_research_workflow.py` | Multi-domain | Full workflow: DB + solve + sweep |
| `ex09_cantera_cea.py` | Combustion | Cantera adapter, propellant comparison |
| `ex10_detonation.py` | Combustion | NASA CEA adapter, CJ detonation |
| `ex11_ode_solvers.py` | Multi-domain | ODE, BVP, 1D PDE heat equation |
| `ex12_project_registry.py` | Workflow | Project store, promote to global |
| `ex13_controls_analysis.py` | Controls | PID tuning, stability analysis |
| `ex14_materials_fatigue.py` | Materials | Fatigue life, Miner's rule, fracture |
| `ex15_aero_performance.py` | Aero | ISA atmosphere, drag polar, Breguet range |
| `ex16_optimization.py` | Multi-domain | Global optimization, DE/SHGO |
| `ex17_rayleigh_flow.py` | Aero/Thermo | Rayleigh flow with heat addition |
| `ex18_decomp.py` | Decomposition | POD, DMD, low-rank reconstruction |
| `ex19_abel.py` | Decomposition | Abel inverse/forward, spectroscopy |
| `ex20_space_dynamics.py` | Orbital | Multi-maneuver missions |
| `ex21_poliastro_adapter.py` | Orbital | poliastro adapter, orbit design |
| `ex22_pykep_adapter.py` | Trajectory | pykep adapter, Lambert arcs |
| `ex_signal_processing.py` | Signal | FFT, STFT, filter, envelope, xcorr |
| `ex_xfoil_adapter.py` | Aero | XFOIL 2D airfoil polars |
| `ex_openfoam_adapter.py` | CFD | OpenFOAM simpleFoam/rhoSimpleFoam |
| `ex_su2_adapter.py` | CFD | SU2 Euler/RANS, wave drag onset |
| `ex_openmdo_adapter.py` | MDO | OpenMDAO Sellar benchmark, beam |
| `ex_fenics_adapter.py` | FEM | FEniCSx elasticity, heat conduction |
| `ex_pynastran_adapter.py` | FEM | NASTRAN SOL 101/103, modal analysis |
| `ex_surrogate_adapter.py` | Surrogate | GP, polynomial, RBF surrogates |

## Documentation

- `docs/ANVIL_GUIDE.html` — Interactive guide (open in browser)
- `docs/ANVIL_WIKI.html` — Complete reference wiki (open in browser)
- `docs/wiki/` — Wiki source pages (Markdown)
  - `09_builtin_rsqs.md` — All 87 RSQs with signatures and examples
  - `10_adapters.md` — Adapter pattern guide + all adapter reference
  - `19_signal_processing.md` — Signal processing RSQs reference

## Requirements

- Python 3.10+
- NumPy >= 1.24
- SciPy >= 1.11
- matplotlib >= 3.7 (optional, for visualization)
- scikit-learn >= 1.3 (optional, for GP surrogate adapter)
- pyNASTRAN >= 1.3 (optional, for NASTRAN FEM adapter)
- openmdao >= 3.27 (optional, for OpenMDAO MDO adapter)
- fenics-dolfinx (optional, conda-forge; for FEniCSx FEM adapter)
- cantera >= 3.0 (optional, for combustion adapter)
- poliastro >= 0.17 (optional, for orbital adapter)
- pykep >= 2.6 (optional, for trajectory adapter)
