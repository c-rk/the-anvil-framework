# Adapters

An `Adapter` wraps an external tool — Python library, CLI executable, Fortran solver — as a native Anvil Relation. Once wrapped, it plugs into Systems, participates in solves, sweeps, and sensitivity analysis, identically to plain Python functions.

`Adapter` is a subclass of `Relation`. It appears as a normal Relation to all System machinery.

---

## Two Backends

| Backend | Use for |
|---------|---------|
| `"python"` | Python library calls (CoolProp, Cantera, OpenMDAO, Pint) |
| `"cli"` | Command-line executables (SU2, OpenFOAM, custom Fortran/C codes) |

---

## Python Backend

```python
from anvil import Adapter, Q

adapter = Adapter("adapter_name",
    backend="python",
    call=_wrapper_function,
    inputs={
        "param1": {"unit": "Pa", "desc": "Pressure", "default": 101325},
        "param2": {"unit": "K",  "desc": "Temperature"},
    },
    outputs={
        "out1": {"unit": "kg/m^3", "desc": "Density"},
        "out2": {"desc": "Dimensionless ratio"},
    },
    desc="Short description",
    tags=["tag1", "tag2"],
)
```

### Input spec fields

| Field | Required | Description |
|-------|----------|-------------|
| `"unit"` | No | Tool expects this unit. Anvil converts from SI before calling wrapper. |
| `"desc"` | No | Human description |
| `"default"` | No | Default value if not in System workspace |

### Output spec fields

| Field | Required | Description |
|-------|----------|-------------|
| `"unit"` | No | Tool returns in this unit. Anvil wraps with `Q(v, unit)`. |
| `"desc"` | No | Human description |

### How the wrapper function receives inputs

**Inputs arrive as raw SI floats.** The adapter automatically converts from SI to the tool's declared unit:

```python
# Declared: "P": {"unit": "Pa"}  — same as SI, no conversion needed
# Declared: "T_C": {"unit": "K"}  — if tool wants Celsius, convert INSIDE wrapper:

def _wrapper(P, T_C):
    T_celsius = T_C - 273.15   # convert K → °C inside wrapper
    result = my_tool(P_pascal=P, T_celsius=T_celsius)
    return {"rho": Q(result["density"], "kg/m^3")}
```

### Non-numeric inputs (strings, flags, arrays)

**String and boolean inputs bypass unit conversion entirely.** Omit the `"unit"` field; the value passes through as-is:

```python
# String parameter -- no unit field
inputs={
    "fuel":     {"desc": "Fuel species: H2, CH4, C3H8", "default": "H2"},
    "oxidizer": {"desc": "Oxidizer: O2, air"},
}

def _wrapper(fuel, oxidizer, T):
    # fuel and oxidizer arrive as Python strings, T arrives as SI float
    result = my_tool(fuel=fuel, ox=oxidizer, temp=T)
    return {"Tc": Q(result["T"], "K")}
```

**Vector inputs** must be flattened to named scalar components. Anvil's workspace stores named scalars, not arrays. pykep and poliastro adapters follow this pattern:

```python
# Do this -- one input per component
inputs={
    "r_x": {"unit": "m"}, "r_y": {"unit": "m"}, "r_z": {"unit": "m"},
}

# Do NOT declare an array input -- Anvil cannot wire an array into the workspace
# inputs={"r": {"unit": "m"}}  # wrong
```

Inside the wrapper, reassemble the vector:

```python
def _wrapper(r_x, r_y, r_z, v_x, v_y, v_z, dt, mu):
    r0 = [r_x, r_y, r_z]      # reassemble inside wrapper
    v0 = [v_x, v_y, v_z]
    r1, v1 = propagate(r0, v0, dt, mu)
    return {"r_x_f": Q(r1[0], "m"), ...}
```

### Mock mode pattern

When the external library is optional, wrap the import in `try/except ImportError` and fall back to an analytical or simplified implementation. This lets code using the adapter run — and lets Systems, sweeps, and tests execute — without the dependency installed.

```python
def _wrapper(P, T):
    try:
        import CoolProp.CoolProp as CP
        rho = CP.PropsSI('D', 'P', P, 'T', T, 'Water')
    except ImportError:
        # Ideal gas fallback: not accurate but prevents ImportError at runtime
        rho = P / (461.5 * T)   # water vapour approximation

    return {"rho": Q(rho, "kg/m^3")}
```

**Rules for good mock mode:**
- Import the external library **inside** the wrapper function (lazy import). This way the adapter file loads and the adapter object is created even when the library is missing.
- If an exact analytical fallback exists (e.g., vis-viva for Hohmann, Lagrange coefficients for Keplerian propagation), use it — the mock then returns physically correct values.
- If no clean fallback exists (e.g., Lambert's problem), raise `ImportError` with a clear install message rather than returning wrong values silently.
- Document which adapters have mocks and which require the library.

### How outputs are processed

If the wrapper returns a `Q` object, it's used directly. If it returns a plain float with a declared unit, the adapter wraps it as `Q(v, unit)`. If no unit is declared, it's passed through as a raw float.

### Full example — CoolProp water properties

```python
def _coolprop_water(P, T):
    try:
        import CoolProp.CoolProp as CP
    except ImportError:
        raise ImportError("CoolProp required: pip install CoolProp")

    return {
        "rho": Q(CP.PropsSI('D', 'P', P, 'T', T, 'Water'), "kg/m^3"),
        "mu":  Q(CP.PropsSI('V', 'P', P, 'T', T, 'Water'), "Pa*s"),
        "cp":  Q(CP.PropsSI('C', 'P', P, 'T', T, 'Water'), "J/kg/K"),
        "k":   Q(CP.PropsSI('L', 'P', P, 'T', T, 'Water'), "W/m/K"),
    }

water_props = Adapter("coolprop_water",
    backend="python",
    call=_coolprop_water,
    inputs={
        "P": {"unit": "Pa", "desc": "Pressure",    "default": 101325},
        "T": {"unit": "K",  "desc": "Temperature", "default": 300},
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

**Key rule:** Import the external library **inside** the wrapper function (lazy import). This way the adapter file loads even if CoolProp isn't installed.

---

## CLI Backend

```python
adapter = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD flow.cfg",     # runs in workdir; no format placeholders needed
    inputs={"mach": {}, "alpha_deg": {}, "Re": {}},
    outputs={"CL": {}, "CD": {}, "CM": {}},
    setup=write_config_fn,          # function(inputs_dict, workdir) — write config
    parse=read_results_fn,          # function(workdir) → dict — read outputs
    timeout=300,                    # seconds before kill
    cwd="./su2_runs",               # persistent workdir; None = temp dir (auto-deleted)
)
```

### Execution sequence

1. `setup(inputs_dict, workdir)` — write all config files, meshes, etc.
2. `subprocess.run(command, cwd=workdir, timeout=timeout)` — run the executable
3. `parse(workdir) → dict` — read all output files
4. Outputs wrapped with declared units
5. If `cwd=None`: temp dir created, cleaned up after each call

**Return code check:** If exit code ≠ 0, raises `RuntimeError` with stdout/stderr excerpt (200 chars).

### Full example — SU2 Euler solver

```python
import os

def write_su2_config(inputs, workdir):
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
    history_file = os.path.join(workdir, "history.csv")
    with open(history_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    headers = [h.strip() for h in lines[0].split(",")]
    last    = [v.strip() for v in lines[-1].split(",")]
    row = dict(zip(headers, last))
    return {"CL": float(row["CL"]), "CD": float(row["CD"]), "CM": float(row["CMz"])}

su2 = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD flow.cfg",
    inputs={
        "mach":      {"desc": "Freestream Mach number"},
        "alpha_deg": {"desc": "Angle of attack (degrees)"},
        "Re":        {"desc": "Reynolds number"},
    },
    outputs={"CL": {}, "CD": {}, "CM": {}},
    setup=write_su2_config,
    parse=parse_su2_output,
    timeout=600,
    cwd="./su2_runs",
)
```

---

## Using Adapters in Systems

Once created, adapters work exactly like any other Relation:

```python
pipe = anvil.system("pipe_flow")
pipe.add("P",      500e3, "Pa")
pipe.add("T",      350,   "K")
pipe.add("D_pipe", 0.05,  "m")
pipe.add("V_flow", 2.0,   "m/s")

pipe.use(water_props)                          # rho, mu, cp, k from CoolProp
pipe.use("reynolds_number", map={             # uses rho, mu from adapter
    "L_char": "D_pipe",
    "V":      "V_flow",
})

result = pipe.solve_forward()
result.summary()
```

**Direct call:**

```python
result = water_props(P=101325, T=300)
print(result["rho"])   # Q(998.2, "kg/m^3")
```

**Sweep with adapter:**

```python
import numpy as np
sweep = pipe.sweep("T", np.linspace(280, 370, 20), parallel=4)
sweep.summary(outputs=["rho", "mu", "Re"])
```

---

## Quick Checklist for Writing a New Adapter

Use this as a recipe when asking an LLM or writing an adapter from scratch.

```
1. Write the wrapper function
   - Name it _call or _<adapter_name>_call (private, one per adapter)
   - Import the external library INSIDE the wrapper (lazy import)
   - Add try/except ImportError with fallback or clear install message
   - Inputs arrive as SI floats for numeric params; strings/booleans pass through unchanged
   - Convert to tool's native units inside the wrapper (e.g., m -> km for poliastro)
   - Return a dict of {key: Q(value, "unit")} for all outputs

2. Declare the Adapter object
   - name: lowercase_with_underscores, globally unique
   - backend: "python" (library call) or "cli" (subprocess)
   - inputs spec: numeric inputs get "unit" (SI unit); strings/flags omit "unit"; add "default" if optional
   - outputs spec: always include "unit" so downstream Systems know the dimension
   - desc: one sentence
   - tags: 3-5 keywords for registry search

3. Add a register() function
   - anvil.push(adapter, domain="domain.subdomain", tags=[...])

4. Add if __name__ == "__main__": with a 3-5 line smoke test
   - Call the adapter directly with concrete values
   - Print results so output is verifiable

5. Save to adapters/<library_name>.py
```

**Vector inputs checklist:** If the tool takes a position/velocity vector:
- Flatten to `r_x`, `r_y`, `r_z` scalar inputs
- Reassemble `r = [r_x, r_y, r_z]` inside the wrapper
- Return components as `r_x_f`, `r_y_f`, `r_z_f`

---

## Built-in Cantera Adapters

Located in `anvil/adapters/cantera_thermo.py`. Require `conda install -c cantera cantera`.

```python
from cantera_thermo import cea_rocket, equilibrium_flame, register
```

### `cea_rocket` — Rocket equilibrium

Inputs: `fuel`, `oxidizer`, `OF`, `Pc`, `T_fuel`, `T_ox`
Outputs: `Tc [K]`, `gamma_c`, `R_gas_c [J/kg/K]`, `MW_c [kg/mol]`, `rho_c [kg/m³]`, `cstar [m/s]`

```python
r = cea_rocket(fuel="H2", oxidizer="O2", OF=6.0, Pc=10e6)
# Tc ≈ 3400 K  gamma_c ≈ 1.2  cstar ≈ 2380 m/s
```

### `equilibrium_flame` — Adiabatic flame temperature

Inputs: `fuel`, `oxidizer`, `phi`, `T_init`, `P`
Outputs: `T_ad [K]`, `gamma`, `MW [kg/mol]`, `rho [kg/m³]`

### `register()` — push both to global registry

```python
register()   # pushes cea_rocket and equilibrium_flame under domain "propulsion.combustion"
```

**Mock mode:** The adapters detect whether Cantera is installed. If not, they return physically plausible placeholder values so code that uses them can be tested without Cantera. See `examples/ex09_cantera_cea.py`.

---

## Registering Adapters

```python
# Global registry
anvil.push(water_props, domain="fluid.water", tags=["coolprop", "water"])
anvil.R.coolprop_water(P=101325, T=300)

# Project registry
proj = anvil.project("hx_study", path="./work")
proj.push(water_props, domain="fluid")
proj.R.coolprop_water(P=101325, T=300)
```

### Standard adapter file layout

```python
"""
Anvil adapter for CoolProp — water thermophysical properties.

Requirements:
    pip install CoolProp
"""
from anvil import Adapter, Q


def _call(P, T):
    try:
        import CoolProp.CoolProp as CP
    except ImportError:
        raise ImportError("CoolProp required.\n  Install: pip install CoolProp")
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
    import anvil
    anvil.push(adapter, domain="fluid.water")


if __name__ == "__main__":
    r = adapter(P=101325, T=300)
    print(f"Water density at STP: {r['rho']}")
```

---

## Adapter Inspection

```python
print(adapter.info())
# Adapter: coolprop_water  (backend: python)
#   Water density via CoolProp
#   Inputs:
#     P [Pa] = 101325  -- Pressure
#     T [K]            -- Temperature
#   Outputs:
#     rho [kg/m^3]     -- Water density
#   Tags: fluid, water, coolprop

anvil.check("coolprop_water")   # after registering
```

---

## Unit Handling in Adapters

Anvil always passes SI floats to the wrapper. The `"unit"` field in `inputs` spec tells Anvil to divide the SI value by the unit scale first:

```python
# If "P": {"unit": "bar"}
# Workspace has P = 100000 Pa (SI)
# scale("bar") = 1e5
# Wrapper receives P = 100000 / 1e5 = 1.0 bar
```

For the outputs spec:
- If wrapper returns `Q(val, "unit")` → used directly, unit info from Q
- If wrapper returns plain float and `"unit"` is declared → wrapped as `Q(float, "unit")`
- If wrapper returns plain float and no `"unit"` → raw float in workspace

```python
# Celsius example — degC / °C are supported since v1.3
inputs={"T": {"unit": "degC"}}   # wrapper receives value in °C
# Or declare in K and convert inside:
inputs={"T": {"unit": "K"}}
def _wrapper(T):   # T arrives in Kelvin (SI)
    T_celsius = T - 273.15
    result = tool(T_c=T_celsius)
    return {"rho": Q(result["rho"], "kg/m^3")}
```

**Supported units for `"unit"` field:** Any unit string in the Anvil unit database (see [Unit Engine](03_units.md#complete-unit-table) for full list). Compound units like `"g/s"`, `"W/m^2"` also work.

---

## poliastro Adapter (Orbital Mechanics)

Located in `anvil/adapters/poliastro_orbits.py`. Require `pip install poliastro astropy`.
All three adapters fall back to exact analytical two-body solutions when poliastro is not installed.

```python
from anvil.adapters.poliastro_orbits import poliastro_orbit, poliastro_hohmann, poliastro_propagate, register
```

### `poliastro_orbit` — Keplerian elements to ECI state

Inputs: `a [m]`, `ecc`, `inc [rad]`, `raan [rad]`, `argp [rad]`, `nu [rad]`, `mu (default: Earth)`
Outputs: `r_x, r_y, r_z [m]`, `v_x, v_y, v_z [m/s]`, `r_mag [m]`, `v_mag [m/s]`, `period [s]`, `r_apoapsis [m]`, `r_periapsis [m]`

```python
import math
r = poliastro_orbit(a=6778e3, ecc=0.0, inc=math.radians(51.6),
                     raan=0.0, argp=0.0, nu=0.0)
# period ≈ 5556 s   v_mag ≈ 7669 m/s
```

### `poliastro_hohmann` — Hohmann transfer delta-v

Inputs: `a_i [m]`, `a_f [m]`, `mu (default: Earth)`
Outputs: `dv_1 [m/s]`, `dv_2 [m/s]`, `dv_total [m/s]`, `t_transfer [s]`, `a_transfer [m]`

```python
r = poliastro_hohmann(a_i=6578e3, a_f=42164e3)
# dv_total ≈ 3930 m/s   t_transfer ≈ 18928 s (5.26 h)
```

### `poliastro_propagate` — Orbit propagation by time

Inputs: Keplerian elements + `dt [s]`, `mu (default: Earth)`
Outputs: `r_x, r_y, r_z [m]`, `v_x, v_y, v_z [m/s]`, `nu_f [rad]`

```python
r = poliastro_propagate(a=6778e3, ecc=0.0, inc=0.0, raan=0.0, argp=0.0,
                         nu=0.0, dt=1380.0)  # quarter orbit
# nu_f ≈ π/2  (90 deg)
```

### `register()` — push to global registry

```python
register()   # domain "orbital.poliastro"
anvil.R.poliastro_hohmann(a_i=6578e3, a_f=42164e3)
```

See `examples/ex21_poliastro_adapter.py` for a full demonstration including System chaining, sweeps, and sensitivity analysis.

---

## pykep Adapter (Trajectory Design)

Located in `anvil/adapters/pykep_trajectories.py`. Require `pip install pykep`.
`pykep_propagate` and `pykep_planet_state` have analytical mock fallbacks.
`pykep_lambert` requires pykep (no clean fallback for Lambert's problem).

```python
from anvil.adapters.pykep_trajectories import pykep_lambert, pykep_propagate, pykep_planet_state, register
```

All inputs and outputs are in SI (m, m/s, s, m³/s²). pykep uses SI natively.

### `pykep_planet_state` — Planet heliocentric state

Inputs: `planet` (string: "earth", "mars", "venus", ...), `epoch_mjd2000` (days since 2000-01-01.5)
Outputs: `r_x, r_y, r_z [m]`, `v_x, v_y, v_z [m/s]`, `r_mag [m]`, `v_mag [m/s]`

```python
r = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
# r_mag ≈ 1.496e11 m (1 AU)   v_mag ≈ 29780 m/s
```

### `pykep_propagate` — Cartesian state propagation

Inputs: `r_x, r_y, r_z [m]`, `v_x, v_y, v_z [m/s]`, `dt [s]`, `mu (default: Earth)`
Outputs: `r_x_f, r_y_f, r_z_f [m]`, `v_x_f, v_y_f, v_z_f [m/s]`, `r_mag_f [m]`, `v_mag_f [m/s]`

```python
r = pykep_propagate(r_x=r0[0], r_y=r0[1], r_z=r0[2],
                     v_x=v0[0], v_y=v0[1], v_z=v0[2], dt=3600.0)
```

### `pykep_lambert` — Lambert arc *(pykep required)*

Inputs: `r0_x, r0_y, r0_z [m]`, `r1_x, r1_y, r1_z [m]`, `tof [s]`, `mu (default: Sun)`, `cw`, `multi_revs`
Outputs: `v_dep_x, v_dep_y, v_dep_z [m/s]`, `v_arr_x, v_arr_y, v_arr_z [m/s]`, `dv_dep [m/s]`, `dv_arr [m/s]`, `dv_total [m/s]`

```python
sol = pykep_lambert(
    r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
    r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,  r1_z=r_mars["r_z"].si,
    tof=200 * 86400,
)
# dv_dep ≈ 30.1 km/s  (heliocentric departure speed)
```

### `register()` — push to global registry

```python
register()   # domain "trajectory.pykep"
```

See `examples/ex22_pykep_adapter.py` for a full demonstration including Lambert arcs, porkchop sweeps, and a combined LEO-departure + interplanetary-arc mission budget.

---

## XFOIL Adapter (2D Airfoil)

Located in `anvil/adapters/xfoil_airfoil.py`. Requires XFOIL binary on PATH (`xfoil` or `xfoil.exe`).
Mock mode: thin-airfoil theory with Prandtl-Glauert compressibility correction.

```python
from anvil.adapters.xfoil_airfoil import xfoil_polar, xfoil_alpha_sweep, register
```

### `xfoil_polar` — Single operating point

Inputs: `AoA_deg`, `Re`, `Mach`, `airfoil` (name or .dat path), `n_panels`, `n_iter`, `xtr_top`, `xtr_bot`
Outputs: `CL`, `CD`, `CDp`, `CM`, `Top_Xtr`, `Bot_Xtr`, `source`

```python
r = xfoil_polar(AoA_deg=4.0, Re=1e6, Mach=0.1)
print(r["CL"], r["CD"], r["CM"])
# CL ≈ 0.439   CD ≈ 0.00626   source: mock
```

### `xfoil_alpha_sweep` — Full polar

Inputs: `alpha_start`, `alpha_end`, `alpha_step`, `Re`, `Mach`, `airfoil`, `n_panels`, `n_iter`
Outputs: `CL_list`, `CD_list`, `CM_list`, `AoA_list`, `CL_max`, `AoA_LD_max`, `LD_max`, `n_points`, `source`

```python
r = xfoil_alpha_sweep(alpha_start=-4, alpha_end=14, alpha_step=2, Re=1.5e6)
print(f"L/D max = {r['LD_max']:.1f} at {r['AoA_LD_max']:.1f}°")
# L/D max ≈ 63.4 at 4.0°
```

### `register()` — domain `aero.xfoil`

---

## OpenFOAM CFD Adapter

Located in `anvil/adapters/openfoam_cfd.py`. Requires OpenFOAM installed and solver on PATH.
Mock mode: lifting-line theory + Küchemann wave drag.

```python
from anvil.adapters.openfoam_cfd import openfoam_incompressible, openfoam_compressible, register
```

### `openfoam_incompressible` — simpleFoam (low-speed)

Inputs: `case_path`, `U_inf [m/s]`, `alpha_deg`, `rho [kg/m³]`, `nu [m²/s]`, `L_ref [m]`, `A_ref [m²]`, `n_cores`, `solver`
Outputs: `CL`, `CD`, `CM`, `F_lift [N]`, `F_drag [N]`, `Re`, `source`

```python
r = openfoam_incompressible(case_path="./my_case", U_inf=50.0, alpha_deg=5.0)
print(r["CL"], r["CD"], r["F_lift"])
# CL ≈ 0.548   CD ≈ 0.0062   source: mock (or openfoam if case exists)
```

**Case requirements:** prepared OpenFOAM case with mesh (blockMesh or snappyHexMesh already run), `0/U`, `0/p`, `system/controlDict` with `forceCoeffs` function object.

### `openfoam_compressible` — rhoSimpleFoam (transonic/supersonic)

Inputs: `case_path`, `U_inf [m/s]`, `alpha_deg`, `p_inf [Pa]`, `T_inf [K]`, `gamma`, `L_ref`, `A_ref`, `n_cores`, `solver`
Outputs: `CL`, `CD`, `CM`, `Mach`, `F_lift [N]`, `F_drag [N]`, `source`

```python
r = openfoam_compressible(case_path="./transonic_case", U_inf=272.0, alpha_deg=3.0)
print(r["CL"], r["Mach"])
# Mach ≈ 0.80  CL ≈ 0.196
```

### `register()` — domain `cfd.openfoam`

---

## SU2 CFD Adapter

Located in `anvil/adapters/su2_aero.py`. Requires `SU2_CFD` on PATH.
Mock mode: Prandtl-Glauert lift + Prandtl-Schlichting skin friction.

```python
from anvil.adapters.su2_aero import su2_euler, su2_rans, register
```

### `su2_euler` — Inviscid Euler

Inputs: `cfg_template` (.cfg file path), `mesh` (.su2 mesh path), `Mach`, `AoA_deg`, `sideslip_deg`, `alpha0_deg`
Outputs: `CL`, `CD`, `CM`, `Mach`, `source`

```python
r = su2_euler(cfg_template="naca0012.cfg", mesh="naca0012.su2",
              Mach=0.3, AoA_deg=4.0)
print(r["CL"], r["CD"])
# CL ≈ 0.439   CD ≈ 0.00129 (induced only, no friction)
```

### `su2_rans` — Turbulent RANS (Spalart-Allmaras)

Inputs: same as `su2_euler` + `Reynolds`
Outputs: `CL`, `CD`, `CM`, `Mach`, `Re`, `source`

```python
r = su2_rans(cfg_template="naca0012_sa.cfg", mesh="naca0012.su2",
             Mach=0.3, AoA_deg=4.0, Reynolds=3e6)
print(r["CL"], r["CD"])
# CL ≈ 0.439   CD ≈ 0.00589 (pressure + friction)
```

**Config patching:** The adapter patches `MACH_NUMBER`, `AOA`, `SIDESLIP_ANGLE`, and optionally `REYNOLDS_NUMBER` in the template. All other settings (numerics, mesh filename path handling, BCs) come from the template.

### `register()` — domain `cfd.su2`

---

## OpenMDAO MDO Adapter

Located in `anvil/adapters/openmdo_wrap.py`. Requires `pip install openmdao`.
Mock mode: analytical Sellar equations (iterative coupling), Euler-Bernoulli beam.

```python
from anvil.adapters.openmdo_wrap import make_openmdo_adapter, openmdo_sellar, openmdo_beam, register
```

### `make_openmdo_adapter` — Factory for any OpenMDAO Problem

```python
def build_prob():
    import openmdao.api as om
    # ... set up components ...
    p = om.Problem()
    p.setup()
    return p

adapter = make_openmdo_adapter(
    prob_factory=build_prob,
    input_vars={"x": {"unit": "1", "desc": "Input", "default": 0.0}},
    output_vars={"f": {"unit": "1", "desc": "Output"}},
    name="my_mdo",
    run_driver=False,     # True = optimize, False = single analysis
)
r = adapter(x=3.0)
```

### `openmdo_sellar` — Sellar coupled MDO benchmark

Inputs: `x1`, `z1`, `z2` (dimensionless)
Outputs: `f` (objective), `g1`, `g2` (constraints ≤ 0), `y1`, `y2` (coupling), `source`

```python
r = openmdo_sellar(x1=1.0, z1=5.0, z2=2.0)
print(r["f"], r["g1"], r["g2"])
# f ≈ 28.6  g1 ≈ -22.4 (feasible)  g2 ≈ -12.1 (feasible)
```

### `openmdo_beam` — Cantilever beam ExplicitComponent

Inputs: `F_tip [N]`, `L_beam [m]`, `E [Pa]`, `b [m]`, `h [m]`
Outputs: `deflection [m]`, `max_stress [Pa]`, `I_moment [m⁴]`, `source`

```python
r = openmdo_beam(F_tip=5000, L_beam=2.0, E=70e9, b=0.05, h=0.10)
print(r["deflection"], r["max_stress"])
# deflection ≈ 0.0366 m   max_stress ≈ 480 MPa
```

### `register()` — domain `mdo.openmdao`

---

## FEniCSx FEM Adapter

Located in `anvil/adapters/fenics_fem.py`. Requires `conda install -c conda-forge fenics-dolfinx mpi4py`.
Mock mode: Euler-Bernoulli beam (elasticity), 1D Fourier + volumetric source (heat).

```python
from anvil.adapters.fenics_fem import fenics_linear_elasticity, fenics_heat_conduction, register
```

### `fenics_linear_elasticity` — 3D box linear elasticity

Inputs: `E [Pa]`, `nu`, `Lx [m]`, `Ly [m]`, `Lz [m]`, `F_distributed [Pa]`, `nx`, `ny`, `nz`
Outputs: `max_displacement [m]`, `max_von_mises [Pa]`, `source`

```python
r = fenics_linear_elasticity(E=200e9, nu=0.3,
    Lx=1.0, Ly=0.05, Lz=0.05,
    F_distributed=1e4)
print(r["max_displacement"], r["max_von_mises"])
# max_displacement ≈ 1.15e-4 m   max_von_mises ≈ 2.4 MPa
```

**Setup:** Cantilever fixed at `x=0`, distributed traction on top face (`z=Lz`).

### `fenics_heat_conduction` — 3D steady heat conduction

Inputs: `k [W/m/K]`, `Lx`, `Ly`, `Lz [m]`, `T_left [K]`, `T_right [K]`, `Q_vol [W/m³]`, `nx`, `ny`, `nz`
Outputs: `T_max [K]`, `heat_flux [W]`, `source`

```python
r = fenics_heat_conduction(k=205.0, Lx=0.5, Ly=0.02, Lz=0.02,
                            T_left=600.0, T_right=300.0)
print(r["T_max"], r["heat_flux"])
# T_max = 600 K   heat_flux ≈ 9.84 W
```

### `register()` — domain `fem.fenics`

---

## pyNASTRAN / NASTRAN Adapter

Located in `anvil/adapters/pynastran_fem.py`. Requires `pip install pyNASTRAN`.
NASTRAN binary auto-detected: MYSTRAN (free), MSC NASTRAN, NX NASTRAN, Optistruct.
Mock mode: Euler-Bernoulli static + analytical cantilever frequencies (βₙL values).

```python
from anvil.adapters.pynastran_fem import nastran_linear_static, nastran_normal_modes, register
```

### `nastran_linear_static` — SOL 101

Inputs: `bdf_path`, `load_case_id`, `E_fallback [Pa]`, `I_fallback [m⁴]`, `L_fallback [m]`, `F_fallback [N]`, `nastran_bin`
Outputs: `max_displacement [m]`, `max_stress [Pa]`, `source`

```python
r = nastran_linear_static(bdf_path="my_model.bdf", load_case_id=1)
print(r["max_displacement"], r["max_stress"])
# max_displacement ≈ 8.0e-5 m (or from OP2 if NASTRAN runs)
```

### `nastran_normal_modes` — SOL 103

Inputs: `bdf_path`, `n_modes`, `E_fallback`, `I_fallback`, `L_fallback`, `rho_fallback`, `A_fallback`, `nastran_bin`
Outputs: `frequencies [list of Q]`, `f1 [Hz]`, `f2 [Hz]`, `n_modes`, `source`

```python
r = nastran_normal_modes(bdf_path="my_model.bdf", n_modes=6)
print(r["f1"], r["frequencies"])
# f1 ≈ 14.3 Hz   (1st bending mode of steel cantilever, L=1m, 50×50mm)
```

**MYSTRAN (free solver):** Download from `https://github.com/dr-bill-c/MYSTRAN`. Add `mystran.exe` to PATH. The adapter auto-detects it.

### `register()` — domain `fem.nastran`

---

## Surrogate / Metamodel Adapters

Located in `anvil/adapters/surrogate_models.py`. Requires `pip install scikit-learn` for GP. Polynomial and RBF work with numpy/scipy only.

```python
from anvil.adapters.surrogate_models import (
    make_gp_adapter, make_poly_adapter, make_rbf_adapter, gp_demo, register
)
```

### `make_gp_adapter` — Gaussian Process from training data

```python
import numpy as np
X_train = np.linspace(0, 10, 15).reshape(-1, 1)
y_train = np.sin(X_train.ravel()) + 0.02 * np.random.randn(15)

gp = make_gp_adapter(
    X_train, y_train,
    x_name="x", y_name="y_pred",
    x_unit="m", y_unit="1",
    name="sin_gp",
)
r = gp(x=3.14)
print(r["y_pred"], r["y_pred_std"])   # mean prediction + uncertainty
```

Falls back to cubic spline (scipy) when sklearn is not installed.

### `make_poly_adapter` — Polynomial chaos / polyfit

```python
poly = make_poly_adapter(X_train, y_train,
    x_name="x", y_name="y_pred",
    degree=4, name="sin_poly")
r = poly(x=3.14)
# Works with numpy only, always available
```

### `make_rbf_adapter` — RBF interpolation (multi-input)

```python
X_2d = np.column_stack([aoa_vals, mach_vals])   # shape (n, 2)
rbf  = make_rbf_adapter(X_2d, cl_vals,
    input_names=["AoA_deg", "Mach"],
    y_name="CL_pred",
    function="multiquadric",
    name="cl_rbf",
)
r = rbf(AoA_deg=5.0, Mach=0.3)
# Requires scipy (always available as Anvil dependency)
```

### `gp_demo` — Pre-built demo GP (noisy sine)

```python
r = gp_demo(x=1.57)
print(r["y_pred"], r["y_exact"])   # GP prediction vs exact sin(x)
```

### Surrogates in Systems

```python
sys_ = anvil.system("drag_polar")
sys_.add("AoA_deg", 0.0)
sys_.use(gp_cd)   # gp_cd = make_gp_adapter(...)

sweep = sys_.sweep("AoA_deg", np.linspace(-4, 14, 10))
```

### `register()` — domain `surrogate.demo`

---

## Adapter Comparison

| Adapter file | Library | Mock? | Domain | Best for |
|---|---|---|---|---|
| `cantera_thermo.py` | Cantera | Yes (curve fits) | `propulsion.combustion` | Combustion, flame temperature |
| `nasa_cea_detonation.py` | NASA CEA CLI | CLI | `propulsion.detonation` | Detonation products |
| `poliastro_orbits.py` | poliastro | Yes (analytical) | `orbital.poliastro` | Orbit design, Hohmann transfers |
| `pykep_trajectories.py` | pykep | Partial | `trajectory.pykep` | Lambert arcs, interplanetary trajectory |
| `xfoil_airfoil.py` | XFOIL CLI | Yes (thin-airfoil) | `aero.xfoil` | 2D airfoil polars, viscous drag |
| `openfoam_cfd.py` | OpenFOAM | Yes (lifting-line) | `cfd.openfoam` | 3D CFD, incompressible/compressible |
| `su2_aero.py` | SU2_CFD | Yes (Prandtl-Glauert) | `cfd.su2` | Euler/RANS, adjoint-ready |
| `openmdo_wrap.py` | OpenMDAO | Yes (analytical) | `mdo.openmdao` | MDO problems, coupled systems |
| `fenics_fem.py` | FEniCSx | Yes (beam theory) | `fem.fenics` | FEM elasticity, heat conduction |
| `pynastran_fem.py` | pyNASTRAN | Yes (beam theory) | `fem.nastran` | NASTRAN SOL 101/103, OP2 post-proc |
| `surrogate_models.py` | scikit-learn | Yes (spline/poly) | `surrogate.demo` | Data-driven surrogates, metamodels |

---

## Limitations

| Limitation | Notes |
|-----------|-------|
| `"http"` backend | Not yet implemented |
| `"shared_lib"` backend | Not yet implemented |
| Async CLI tools | Not supported — `subprocess.run` is synchronous |
| Stateful wrappers | Each call is independent; no session state between calls |
| Nested subprocess environments | CLI adapters inherit the parent process environment; path issues may arise |
| Thread safety | Python adapters are called from `ThreadPoolExecutor` in parallel sweeps; ensure wrapper function is thread-safe |
| Array inputs | Anvil workspace is scalar-keyed; flatten vectors to named components |
| String inputs in sweeps | `sys.sweep()` sweeps over numeric ranges; string parameters must be fixed at System level |
| Registry round-trip | `anvil.push(adapter)` stores the inner wrapper closure, losing the `inputs` spec. **Do not** use `anvil.R.adapter_name` in `sys.use()` — pass the adapter object directly: `sys.use(my_adapter)`. Register for discoverability only. |
