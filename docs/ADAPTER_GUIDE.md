# Anvil Framework — Adapter Guide

**Version 1.1.0** | Integrating External Tools into Anvil

---

## Contents

1. [What is an Adapter?](#1-what-is-an-adapter)
2. [Python Backend — step by step](#2-python-backend--step-by-step)
3. [CLI Backend — step by step](#3-cli-backend--step-by-step)
4. [Using Adapters in Systems](#4-using-adapters-in-systems)
5. [Adapter File Structure](#5-adapter-file-structure)
6. [Registering Adapters](#6-registering-adapters)
7. [Built-in Cantera Adapters](#7-built-in-cantera-adapters)
8. [Unit Handling Reference](#8-unit-handling-reference)
9. [Verifying Adapters](#9-verifying-adapters)
10. [AI Agent Prompt — Generate an Adapter Automatically](#10-ai-agent-prompt--generate-an-adapter-automatically)

---

## 1. What is an Adapter?

An Adapter wraps an external tool — a Python library, a CLI executable, a Fortran solver — so it behaves exactly like any other Anvil Relation. Once wrapped, it plugs into Systems, participates in solves, sweeps, sensitivity analysis, and composition, identically to a plain Python function.

**Two backends:**

- **`"python"`** — calls a Python function directly (CoolProp, Cantera, OpenMDAO, Pint, ...)
- **`"cli"`** — runs a command-line executable (SU2, OpenFOAM, custom Fortran/C codes)

---

## 2. Python Backend — Step by Step

### Step 1: Write the wrapper function

The wrapper receives raw SI floats from Anvil's solver workspace and returns a dict. Import the external library **inside** the function (lazy import) so the adapter file loads even if the package is not installed.

```python
def _coolprop_water(P, T):
    """
    Water thermophysical properties via CoolProp.
    P [Pa], T [K] → rho, mu, cp, k
    """
    try:
        import CoolProp.CoolProp as CP
    except ImportError:
        raise ImportError(
            "CoolProp is required for this adapter.\n"
            "  Install: pip install CoolProp"
        )
    rho = CP.PropsSI('D', 'P', P, 'T', T, 'Water')
    mu  = CP.PropsSI('V', 'P', P, 'T', T, 'Water')
    cp  = CP.PropsSI('C', 'P', P, 'T', T, 'Water')
    k   = CP.PropsSI('L', 'P', P, 'T', T, 'Water')
    return {
        "rho": Q(rho, "kg/m^3"),
        "mu":  Q(mu,  "Pa*s"),
        "cp":  Q(cp,  "J/kg/K"),
        "k":   Q(k,   "W/m/K"),
    }
```

**Rules:**
- Inputs arrive as **raw SI floats** (Anvil converts from whatever unit the System uses)
- Return `Q(value, "unit")` for dimensional outputs — this propagates units to results
- Return plain floats for dimensionless outputs

### Step 2: Declare the Adapter

```python
from anvil import Adapter, Q

water_props = Adapter("coolprop_water",
    backend="python",
    call=_coolprop_water,
    inputs={
        "P": {"unit": "Pa",  "desc": "Pressure",    "default": 101325},
        "T": {"unit": "K",   "desc": "Temperature", "default": 300},
    },
    outputs={
        "rho": {"unit": "kg/m^3", "desc": "Density"},
        "mu":  {"unit": "Pa*s",   "desc": "Dynamic viscosity"},
        "cp":  {"unit": "J/kg/K", "desc": "Specific heat"},
        "k":   {"unit": "W/m/K",  "desc": "Thermal conductivity"},
    },
    desc="Water thermophysical properties via CoolProp",
    tags=["fluid", "water", "coolprop"],
)
```

**`inputs` spec fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `"unit"` | No | Anvil converts from SI to this before calling wrapper. E.g., `"Pa"` → wrapper receives Pa float |
| `"desc"` | No | Human description |
| `"default"` | No | Default value if not provided |

**`outputs` spec fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `"unit"` | No | Expected output unit — used for display. If wrapper returns `Q()` objects, this is informational |
| `"desc"` | No | Human description |

---

## 3. CLI Backend — Step by Step

### Step 1: Write setup and parse functions

```python
import os, json

def write_su2_config(inputs, workdir):
    """Write SU2 config file from Anvil inputs dict."""
    config = f"""
SOLVER= EULER
MACH_NUMBER= {inputs['mach']}
AOA= {inputs['alpha_deg']}
REYNOLDS_NUMBER= {inputs['Re']}
MESH_FILENAME= mesh.su2
OUTPUT_FILES= (RESTART, CSV)
CONV_FIELD= RMS_DENSITY
"""
    with open(os.path.join(workdir, "flow.cfg"), "w") as f:
        f.write(config)

def parse_su2_output(workdir):
    """Read SU2 history CSV and return aerodynamic coefficients."""
    history_file = os.path.join(workdir, "history.csv")
    with open(history_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    headers = [h.strip() for h in lines[0].split(",")]
    last    = [v.strip() for v in lines[-1].split(",")]
    row = dict(zip(headers, last))
    return {
        "CL": float(row["CL"]),
        "CD": float(row["CD"]),
        "CM": float(row["CMz"]),
    }
```

### Step 2: Declare the CLI Adapter

```python
su2 = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD flow.cfg",       # runs in workdir
    inputs={
        "mach":      {"desc": "Freestream Mach number"},
        "alpha_deg": {"desc": "Angle of attack (degrees)"},
        "Re":        {"desc": "Reynolds number"},
    },
    outputs={
        "CL": {"desc": "Lift coefficient"},
        "CD": {"desc": "Drag coefficient"},
        "CM": {"desc": "Pitching moment coefficient"},
    },
    setup=write_su2_config,    # called before running command
    parse=parse_su2_output,    # called after command exits
    timeout=600,               # seconds before killing process
    cwd="./su2_runs",          # persistent working directory; None = temp dir
    desc="SU2 Euler solver for 2D airfoil",
    tags=["aero", "CFD", "su2"],
)
```

**Execution sequence:**
1. `setup(inputs_dict, workdir)` — write config, mesh, etc.
2. `subprocess.run(command, cwd=workdir, timeout=timeout)`
3. `parse(workdir)` — read output files, return dict
4. Outputs are wrapped with declared units (if any)

If `cwd=None`, a temporary directory is created per call and deleted afterwards. If `cwd` is set, it persists across calls (useful for runs that generate large files you want to inspect).

---

## 4. Using Adapters in Systems

Once created, adapters work exactly like any other Relation:

```python
from anvil import System

pipe = System("pipe_flow")
pipe.add("P",      500e3, "Pa")
pipe.add("T",      350,   "K")
pipe.add("D_pipe", 0.05,  "m")
pipe.add("V_flow", 2.0,   "m/s")

pipe.use(water_props)                            # pulls rho, mu, cp, k
pipe.use("reynolds_number", map={               # uses rho, mu from adapter
    "L_char": "D_pipe",
    "V":      "V_flow",
})
pipe.solve_forward().summary()
```

Direct call (no System):

```python
result = water_props(P=101325, T=300)
print(result["rho"])   # Q(998.2, "kg/m^3")
```

Sweep with adapter inside system:

```python
sweep = pipe.sweep("T", np.linspace(280, 370, 20), parallel=4)
sweep.summary(outputs=["rho", "mu", "Re"])
```

---

## 5. Adapter File Structure

For sharing, put each adapter in its own file under `adapters/`:

```
adapters/
    __init__.py
    coolprop_water.py
    cantera_thermo.py
    su2_airfoil.py
    openfoam_pipe.py
```

Standard file layout:

```python
"""
Anvil adapter for CoolProp — water thermophysical properties.

Wraps CoolProp.PropsSI to compute density, viscosity, specific heat,
and thermal conductivity of liquid water.

Requirements:
    pip install CoolProp
"""
from anvil import Adapter, Q


def _call(P, T):
    try:
        import CoolProp.CoolProp as CP
    except ImportError:
        raise ImportError(
            "CoolProp is required for this adapter.\n"
            "  Install: pip install CoolProp"
        )
    rho = CP.PropsSI('D', 'P', P, 'T', T, 'Water')
    return {"rho": Q(rho, "kg/m^3")}


adapter = Adapter("coolprop_water",
    backend="python", call=_call,
    inputs={"P": {"unit": "Pa", "default": 101325},
            "T": {"unit": "K",  "default": 300}},
    outputs={"rho": {"unit": "kg/m^3", "desc": "Water density"}},
    desc="Water density via CoolProp",
    tags=["fluid", "water", "coolprop"],
)


def register():
    """Register this adapter in the Anvil global registry."""
    import anvil
    anvil.push(adapter, domain="fluid.water", tags=["coolprop"])


if __name__ == "__main__":
    # Quick test
    r = adapter(P=101325, T=300)
    print(f"Water density at STP: {r['rho']}")
```

Import and use:

```python
from adapters.coolprop_water import adapter as water
system.use(water)

# Or register globally once and use by name everywhere
from adapters.coolprop_water import register
register()
anvil.R.coolprop_water(P=101325, T=300)
```

---

## 6. Registering Adapters

```python
import anvil

# Register to global registry
anvil.push(water_props, domain="fluid", tags=["water", "coolprop"])
# → available as anvil.R.coolprop_water(...)

# Register to a project only
proj = anvil.project("hx_study", path="./work")
proj.push(water_props, domain="fluid")
# → available as proj.R.coolprop_water(...)
# → does NOT pollute global registry until proj.promote("coolprop_water")
```

---

## 7. Built-in Cantera Adapters

Located at `adapters/cantera_thermo.py`. Require `conda install -c cantera cantera`.

```python
import sys; sys.path.insert(0, "path/to/adapters")
from cantera_thermo import cea_rocket, equilibrium_flame, register
```

### `cea_rocket` — Rocket chamber equilibrium

Equivalent to NASA CEA HP equilibration.

```python
cea_rocket(
    fuel="H2",      # H2, CH4, C2H5OH, C3H8 (or any Cantera species)
    oxidizer="O2",  # O2, or "O2:1,N2:3.76" for air
    OF=6.0,         # oxidizer/fuel mass ratio
    Pc=10e6,        # chamber pressure [Pa]
    T_fuel=300,     # fuel inlet temperature [K]
    T_ox=90,        # oxidizer inlet temperature [K]
)
# Returns: Tc [K], gamma_c, R_gas_c [J/kg/K], MW_c [kg/mol], rho_c [kg/m³], cstar [m/s]
```

### `equilibrium_flame` — Adiabatic flame temperature

```python
equilibrium_flame(
    fuel="CH4",
    oxidizer="O2:1,N2:3.76",  # air
    phi=1.0,                   # equivalence ratio
    T_init=300,                # initial temperature [K]
    P=101325,                  # pressure [Pa]
)
# Returns: T_ad [K], gamma, MW [kg/mol], rho [kg/m³]
```

### Registering

```python
register()   # pushes both adapters to global registry under propulsion.combustion
```

### Full engine example

See `examples/ex09_cantera_cea.py` for a complete H2/O2 and CH4/O2 engine analysis. The example works with or without Cantera installed (uses a mock if not available).

---

## 8. Unit Handling Reference

Anvil uses SI base units internally. The `"unit"` field in an adapter's input spec tells Anvil to convert the SI value **before** passing it to the wrapper. Use this when the external tool expects a non-SI input (e.g., a tool that takes Celsius instead of Kelvin).

```python
inputs={
    "T": {"unit": "K"},     # tool receives Kelvin (same as SI — no conversion)
    "P": {"unit": "Pa"},    # tool receives Pascals (same as SI — no conversion)
    "T_C": {"unit": "K"},   # no Celsius unit; convert manually inside wrapper
}
```

For the `outputs` spec, Anvil wraps plain float outputs with the declared unit:

```python
outputs={"Tc": {"unit": "K"}}
# If wrapper returns {"Tc": 3500.0}, Anvil wraps it as Q(3500.0, "K")
# If wrapper returns {"Tc": Q(3500.0, "K")}, the Q() is used directly
```

**Supported unit strings** (full list in `ANVIL_DOCUMENTATION.md §5.7`):

```
Pressure:     Pa, kPa, MPa, GPa, bar, atm, psi, psia, torr
Temperature:  K, R
Velocity:     m/s, km/s, km/hr, ft/s, mph, kn
Force:        N, kN, MN, lbf
Energy:       J, kJ, MJ, cal, BTU, eV
Power:        W, kW, MW, hp
Mass:         kg, g, mg, lb, tonne
Length:       m, km, cm, mm, um, in, ft
Area:         m^2, cm^2, mm^2, ft^2, in^2
Volume:       m^3, cm^3, L, ft^3, gal
Density:      kg/m^3, g/cm^3, lb/ft^3
Viscosity:    Pa*s, poise, m^2/s
Specific:     J/kg, kJ/kg, J/kg/K, kJ/kg/K, BTU/lb, BTU/lb/R
Thermal:      W/m/K
Molar:        kg/mol, g/mol, J/mol/K
Mass flow:    kg/s, lb/s
Other:        V, Hz, kHz, rad, deg, mol, kmol, A
Compound:     any combination parsed automatically (e.g., g/s, cm/s, mW/m^2)
Dimensionless: "" (empty string)
```

---

## 9. Verifying Adapters

```python
import anvil

# After registering
anvil.check("coolprop_water")
# Shows: type, inputs, outputs, test run with defaults, any issues

# Programmatic
report = anvil.check("coolprop_water", verbose=False)
report["ok"]        # bool
report["inputs"]    # list
report["outputs"]   # list
report["issues"]    # list of problem strings
```

---

## 10. AI Agent Prompt — Generate an Adapter Automatically

Give this prompt to any AI agent (Claude, GPT, Gemini, Copilot) to generate a ready-to-use adapter file. Replace the package name and answer the clarifying questions.

---

```
=== ANVIL FRAMEWORK — ADAPTER GENERATION PROMPT ===

You are generating an Anvil Framework adapter file for the package below.

Anvil is a Python engineering computation framework. Adapters wrap
external tools so they work as native Anvil Relations inside solvable
Systems — participating in solves, parametric sweeps, and composition
exactly like plain Python functions.

PACKAGE TO ADAPT:
[replace with: CoolProp / Cantera / OpenMDAO / SU2 / OpenFOAM / your package]

─────────────────────────────────────────────
ANVIL ADAPTER API
─────────────────────────────────────────────

from anvil import Adapter, Q

adapter = Adapter(
    name="<snake_case_name>",
    backend="python",            # or "cli"
    call=<wrapper_function>,     # python backend
    command="<cmd {arg}>",       # cli backend
    inputs={
        "<param>": {
            "unit": "<unit>",    # SI unit the tool expects; "" = dimensionless
            "desc": "<text>",
            "default": <value>,  # optional
        },
    },
    outputs={
        "<param>": {
            "unit": "<unit>",    # unit the tool returns; "" = dimensionless
            "desc": "<text>",
        },
    },
    setup=<fn(inputs, workdir)>, # cli only
    parse=<fn(workdir) -> dict>, # cli only
    timeout=60,                  # cli only
    desc="<one-line description>",
    tags=["<tag>"],
)

─────────────────────────────────────────────
UNIT STRINGS — use exactly these
─────────────────────────────────────────────

Pressure:     Pa, kPa, MPa, GPa, bar, atm, psi
Temperature:  K, R
Velocity:     m/s, km/s, ft/s, mph
Force:        N, kN, lbf
Energy:       J, kJ, MJ, BTU
Power:        W, kW, MW
Mass:         kg, g, lb
Length:       m, cm, mm, ft, in
Area:         m^2, cm^2, ft^2
Volume:       m^3, cm^3, L
Density:      kg/m^3, g/cm^3
Viscosity:    Pa*s, m^2/s
Sp. heat:     J/kg/K, kJ/kg/K
Sp. energy:   J/kg, kJ/kg
Mass flow:    kg/s, lb/s
Conductivity: W/m/K
Molar:        kg/mol, g/mol, J/mol/K
Dimensionless: ""
Compound:     any combination, e.g. "g/s", "W/m^2", "cm/s"

─────────────────────────────────────────────
RULES
─────────────────────────────────────────────

1. The wrapper function receives raw SI floats. Return a dict.
2. For dimensional outputs, wrap with Q(value, "unit"). For
   dimensionless outputs, return plain floats.
3. Import the external package INSIDE the wrapper (lazy import) so the
   adapter file loads even if the package is not installed.
4. Add a clear ImportError message with install instructions.
5. Add a module docstring: what it wraps, install command, any caveats.
6. Add a register() function: calls anvil.push(adapter, domain=...).
7. Add an if __name__ == "__main__" block that tests the adapter with
   typical input values and prints the result.
8. If the package has many functions, write SEPARATE adapters — one per
   physical model. Never one monolithic adapter with a "mode" parameter.
9. Name adapters descriptively: "coolprop_water_density",
   "cantera_h2o2_flame", "su2_euler_airfoil". Not "adapter1".
10. For CLI adapters, the setup function writes all config files;
    the parse function reads all result files. Both receive raw floats
    (same as the wrapper).

─────────────────────────────────────────────
OUTPUT FORMAT
─────────────────────────────────────────────

Generate a single .py file with this structure:

    """
    Anvil adapter for [PACKAGE].
    [What it computes and wraps.]
    Requirements: pip install [package]  (or conda install ...)
    """
    from anvil import Adapter, Q

    def _wrapper(input1, input2, ...):
        try:
            import package
        except ImportError:
            raise ImportError("[package] required.\n  Install: pip install [package]")
        # call tool, extract outputs
        return {"out1": Q(val, "unit"), "out2": plain_float}

    adapter = Adapter(
        name="...",
        backend="python",
        call=_wrapper,
        inputs={...},
        outputs={...},
        desc="...",
        tags=[...],
    )

    def register():
        import anvil
        anvil.push(adapter, domain="...", tags=[...])

    if __name__ == "__main__":
        r = adapter(input1=..., input2=...)
        for k, v in r.items():
            print(f"  {k}: {v}")

─────────────────────────────────────────────
BEFORE GENERATING — ask the user:
─────────────────────────────────────────────

1. Which specific functions / models from this package do you want?
   (e.g., "PropsSI for water" vs "full mixture library")
2. What are typical input ranges? (for setting sensible defaults)
3. For CLI tools: what does the config file look like, and what does
   the output file look like?
4. Any non-SI units the tool expects? (e.g., Celsius, bar, lb/ft³)

GENERATE THE ADAPTER FILE NOW.
=== END PROMPT ===
```

---

### How to use this prompt

1. Copy the prompt above
2. Replace `[replace with: ...]` with your package name
3. Paste into any AI chat (Claude, GPT, Gemini, Copilot)
4. Answer the clarifying questions if asked
5. Save the output as `adapters/<package_name>.py`
6. Test it:

```python
python adapters/coolprop_water.py          # runs __main__ test
```

7. Use it in Anvil:

```python
from adapters.coolprop_water import adapter as water, register
register()
system.use(water)
# or: anvil.R.coolprop_water(P=101325, T=300)
```
