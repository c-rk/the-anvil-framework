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
# Celsius example (no offset support in UnitDB — convert manually)
inputs={"T": {"unit": "K"}}   # NOT "°C" — not in unit database
# Convert inside wrapper:
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

## Adapter Comparison

| Adapter file | Library | Mock? | Domain | Best for |
|---|---|---|---|---|
| `cantera_thermo.py` | Cantera | Yes (curve fits) | `propulsion.combustion` | Combustion, flame temperature |
| `nasa_cea_detonation.py` | NASA CEA CLI | CLI | `propulsion.detonation` | Detonation products |
| `poliastro_orbits.py` | poliastro | Yes (analytical) | `orbital.poliastro` | Orbit design, Hohmann transfers |
| `pykep_trajectories.py` | pykep | Partial | `trajectory.pykep` | Lambert arcs, interplanetary trajectory |

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
