# NASA CEA Installation Guide & Anvil Integration

**For detonation problems (Chapman-Jouguet) and general combustion analysis**

---

## What is NASA CEA?

NASA's Chemical Equilibrium with Applications (CEA) computes equilibrium compositions via free-energy minimization for complex chemical mixtures. It covers rocket performance, Chapman-Jouguet detonation parameters, and shock-tube analysis, with a thermodynamic database of 2000+ species.

The official modern reimplementation lives at **https://github.com/nasa/cea** (Apache-2.0 license).

---

## Path A: Install from PyPI (Recommended, fastest)

This is the simplest path if you just need the Python API.

```
pip install cea
```

Verify:

```python
import cea
print(cea.__version__)  # Should print 3.x
```

If this works, skip to **"Your First Detonation Problem"** below.

### Troubleshooting PyPI install

The `pip install cea` package ships prebuilt wheels for common platforms. If your platform isn't covered (or you get build errors), you'll need **Path B**.

Common issues:
- **Python version**: Requires Python >= 3.11. Check with `python --version`.
- **Windows without VS Build Tools**: The wheel may need Visual Studio C++ build tools. Install from https://visualstudio.microsoft.com/visual-cpp-build-tools/
- **"No matching distribution"**: Your platform may not have a prebuilt wheel. Use Path B.

---

## Path B: Build from Source (full control)

### Prerequisites

| Tool | Version | How to get it |
|------|---------|---------------|
| **Git** | any | https://git-scm.com |
| **gfortran** | >= 10 | `sudo apt install gfortran` (Linux), Homebrew `brew install gcc` (Mac), or MSYS2/MinGW on Windows |
| **CMake** | >= 3.19 | https://cmake.org or `pip install cmake` |
| **Ninja** | any | `pip install ninja` |
| **Python** | >= 3.11 | https://python.org |

### Step-by-step

**Linux / macOS:**

```bash
# 1. Install build tools (Ubuntu/Debian)
sudo apt update
sudo apt install gfortran ninja-build cmake python3 python3-pip git

# 2. Clone the repo
git clone https://github.com/nasa/cea
cd cea

# 3. Install as Python package (builds everything automatically)
pip install .

# 4. Verify
python -c "import cea; print(cea.__version__)"
```

**Windows (with Intel oneAPI or gfortran via MSYS2):**

```powershell
# 1. Install MSYS2 from https://www.msys2.org
# In MSYS2 terminal:
pacman -S mingw-w64-x86_64-gcc-fortran mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja

# 2. Clone
git clone https://github.com/nasa/cea
cd cea

# 3. Build (from MSYS2 MinGW64 shell or a developer prompt)
pip install .

# 4. Verify
python -c "import cea; print(cea.__version__)"
```

**Windows (WSL alternative -- often simplest):**

```bash
# In WSL Ubuntu terminal:
sudo apt update
sudo apt install gfortran ninja-build cmake python3 python3-pip git
git clone https://github.com/nasa/cea
cd cea
pip install .
python3 -c "import cea; print(cea.__version__)"
```

### Building the CLI executable (optional)

If you want the `cea` command-line tool in addition to the Python API:

```bash
cd cea
cmake --preset dev
cmake --build build-dev
cmake --install build-dev
export PATH="$(pwd)/build-dev/install/bin:$PATH"
cea samples/rp1311_examples.inp    # test it
```

---

## Your First Detonation Problem

### What is a CJ detonation calculation?

Chapman-Jouguet (CJ) detonation computes the equilibrium state behind a self-sustaining detonation wave. CEA finds the CJ point where the detonation products are at sonic velocity relative to the wave. The key outputs are:

- **Detonation velocity** (D_CJ) -- how fast the wave travels
- **Pressure ratio** (P2/P1) -- pressure jump across the wave
- **Temperature** (T2) -- product temperature behind the wave
- **Product composition** -- equilibrium species and mole fractions

### Using the NASA CEA Python API directly

```python
import numpy as np
from cea import DetonationSolver

# Create solver
solver = DetonationSolver()

# Set initial conditions: stoichiometric H2/O2 at 1 atm, 300 K
solver.set_state_property("temperature", 300.0)   # K
solver.set_state_property("pressure", 1.01325)     # bar (CEA uses bar!)
solver.set_reactant_fraction("H2", 2.0)            # 2 moles H2
solver.set_reactant_fraction("O2", 1.0)            # 1 mole O2

# Solve
solution = solver.solve()

# Results
print(f"CJ Detonation velocity:  {solution.detonation_velocity:.1f} m/s")
print(f"CJ Temperature:          {solution.T:.1f} K")
print(f"CJ Pressure:             {solution.P:.4f} bar")
print(f"Pressure ratio (P2/P1):  {solution.P / 1.01325:.2f}")
print(f"Density ratio:           {solution.density:.4f} kg/m3")
print(f"Gamma (isentropic):      {solution.gamma_s:.4f}")
print(f"Molecular weight:        {solution.M:.2f} g/mol")

# Product composition
print(f"\nMajor products:")
for species, frac in sorted(solution.mole_fractions.items(),
                              key=lambda x: -x[1]):
    if frac > 0.001:
        print(f"  {species:12s}  {frac:.4f}")
```

### Note on CEA units

CEA uses its own unit system internally. Key conversions:
- Pressure: **bar** (1 bar = 100,000 Pa)
- Temperature: **K**
- Velocity: **m/s**
- Specific heat: **kJ/(kg*K)**
- Enthalpy: **kJ/kg**

The `cea.units` module provides conversion factors.

---

## Alternative: CEA_Wrap (Community Wrapper)

If the official NASA CEA doesn't install on your system, CEA_Wrap wraps the legacy Fortran executable:

```bash
pip install CEA_Wrap
```

**Note:** On Windows, the Fortran binary (FCEA2.exe) is included. On Mac/Linux you need gfortran to compile it.

**Detonation with CEA_Wrap:**

```python
from CEA_Wrap import DetonationProblem, Material

# Define reactants
H2 = Material("H2", temp=300)  # H2 at 300 K
O2 = Material("O2", temp=300)  # O2 at 300 K

# Create detonation problem at 1 atm
det = DetonationProblem(pressure=1.0)  # atm
det.add_fuel(H2, mol=2.0)
det.add_oxidizer(O2, mol=1.0)

# Run
data = det.run_cea()
print(f"Detonation velocity: {data.det_vel:.1f} m/s")
print(f"CJ Temperature: {data.t:.1f} K")
print(f"CJ Pressure: {data.p:.4f} atm")
```

**Important limitation:** CEA_Wrap's DetonationProblem only works with gaseous reactants (no solids/liquids).

---

## Anvil Framework Integration

### The Adapter (adapters/nasa_cea_detonation.py)

This file wraps NASA CEA's DetonationSolver for use in Anvil Systems.
It's ready to use -- just drop it in your adapters/ directory.

See the adapter file at: `adapters/nasa_cea_detonation.py`

### Usage with Anvil

```python
import anvil
from anvil import System
from adapters.nasa_cea_detonation import cea_detonation

# Direct call: H2/O2 detonation
result = cea_detonation(
    fuel="H2", oxidizer="O2",
    fuel_moles=2.0, ox_moles=1.0,
    T1=300, P1=1.01325
)
print(f"D_CJ = {result['D_CJ'].value:.0f} m/s")
print(f"T_CJ = {result['T_CJ'].value:.0f} K")
print(f"P_ratio = {result['P_ratio']:.2f}")

# In a System with parametric sweep
study = System("detonation_study")
study.add("fuel_moles",  2.0)
study.add("ox_moles",    1.0)
study.add("T1",          300, "K")
study.add("P1",          1.01325)  # bar

def h2o2_det(fuel_moles, ox_moles, T1, P1):
    return cea_detonation(
        fuel="H2", oxidizer="O2",
        fuel_moles=fuel_moles, ox_moles=ox_moles,
        T1=T1, P1=P1
    )
study.use(h2o2_det)

# Sweep over initial pressure
import numpy as np
sweep = study.sweep("P1", np.linspace(0.5, 10, 6))
sweep.summary(outputs=["D_CJ", "T_CJ", "P_ratio"])

# Sensitivity
sens = study.sensitivity(outputs=["D_CJ", "T_CJ"])
sens.summary()
```

---

## Common Detonation Problems to Try

### 1. Stoichiometric H2/Air
```python
# H2 + 0.5(O2 + 3.76 N2) at 1 atm
result = cea_detonation(
    fuel="H2", oxidizer="O2",
    fuel_moles=2.0, ox_moles=1.0,
    T1=300, P1=1.01325,
    extra_species={"N2": 3.76}  # add diluent
)
# Expected: D_CJ ~ 1968 m/s, T_CJ ~ 2949 K
```

### 2. Methane/Oxygen
```python
result = cea_detonation(
    fuel="CH4", oxidizer="O2",
    fuel_moles=1.0, ox_moles=2.0,
    T1=300, P1=1.01325
)
# Expected: D_CJ ~ 2393 m/s, T_CJ ~ 3721 K
```

### 3. Ethylene/Air (typical RDE fuel)
```python
result = cea_detonation(
    fuel="C2H4", oxidizer="O2",
    fuel_moles=1.0, ox_moles=3.0,
    T1=300, P1=1.01325,
    extra_species={"N2": 11.28}
)
```

### 4. Preheated mixture (effect of T1)
```python
# Sweep initial temperature
study.sweep("T1", np.linspace(300, 600, 6))
# Higher T1 -> slightly higher D_CJ, significantly higher T_CJ
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pip install cea` fails | Try Path B (build from source), or use WSL on Windows |
| `ModuleNotFoundError: No module named 'cea'` | Make sure you're in the right Python environment |
| `gfortran: command not found` | Install: `sudo apt install gfortran` (Linux), `brew install gcc` (Mac) |
| `cmake: command not found` | `pip install cmake` or download from cmake.org |
| `ninja: command not found` | `pip install ninja` |
| Detonation gives unexpected results | Check units: CEA uses **bar** for pressure, not Pa |
| CEA_Wrap won't compile on Mac | Follow gfortran install steps in CEA_Wrap Issue #1 |
| Python 3.14 not supported | NASA CEA requires >= 3.11 but may not have wheels for 3.14 yet. Try 3.12. |

---

## References

- NASA CEA GitHub: https://github.com/nasa/cea
- CEA Documentation: https://nasa.github.io/cea/
- CEA Python API: https://nasa.github.io/cea/interfaces/python_api.html
- CEA_Wrap (community): https://github.com/civilwargeeky/CEA_Wrap
- Original NASA RP-1311: https://www.nasa.gov/glenn/research/chemical-equilibrium-with-applications/
