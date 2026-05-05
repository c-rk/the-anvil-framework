# Anvil Framework -- Adapter Guide & AI Agent Prompt

**Version 0.4.0** | Integrating External Tools into Anvil

This document covers two topics:
1. How to write Anvil adapters for external tools (detailed steps + examples)
2. A ready-to-use prompt you can give to any AI agent to generate adapter files automatically

---

## Part 1: Writing Adapters (Step by Step)

### What is an Adapter?

An Adapter wraps an external tool (Python library, CLI program, HTTP service) so it behaves like any other Anvil Relation. Once wrapped, it plugs into Systems, participates in solves, sweeps, and composition -- identically to a plain function.

### The Two Backends

**Python backend** -- for tools with a Python API (CoolProp, Cantera, Pint, custom modules):

```python
from anvil import Adapter

def my_wrapper(P, T):
    """Call the external library and return outputs as a dict."""
    import CoolProp.CoolProp as CP
    rho = CP.PropsSI('D', 'P', P, 'T', T, 'Water')
    mu  = CP.PropsSI('V', 'P', P, 'T', T, 'Water')
    cp  = CP.PropsSI('C', 'P', P, 'T', T, 'Water')
    return {"rho": rho, "mu": mu, "cp": cp}

water_props = Adapter("water_properties",
    backend="python",
    call=my_wrapper,
    inputs={
        "P": {"unit": "Pa", "desc": "Pressure"},
        "T": {"unit": "K",  "desc": "Temperature"},
    },
    outputs={
        "rho": {"unit": "kg/m^3", "desc": "Density"},
        "mu":  {"unit": "Pa*s",   "desc": "Dynamic viscosity"},
        "cp":  {"unit": "J/kg/K", "desc": "Specific heat"},
    },
    desc="Water thermophysical properties via CoolProp",
    tags=["fluid", "water", "properties"],
)
```

**CLI backend** -- for tools that run as executables (SU2, OpenFOAM, custom Fortran):

```python
from anvil import Adapter
import os, json

def write_su2_config(inputs, workdir):
    """Write the SU2 config file from Anvil inputs."""
    config = f\"\"\"
SOLVER= EULER
MACH_NUMBER= {inputs['mach']}
AOA= {inputs['alpha_deg']}
REYNOLDS_NUMBER= {inputs['Re']}
MESH_FILENAME= mesh.su2
\"\"\"
    with open(os.path.join(workdir, "flow.cfg"), "w") as f:
        f.write(config)

def parse_su2_output(workdir):
    """Parse SU2 output files and return dict."""
    # Read forces from SU2 history file
    with open(os.path.join(workdir, "history.csv")) as f:
        lines = f.readlines()
        last = lines[-1].split(",")
    return {"CL": float(last[1]), "CD": float(last[2]), "CM": float(last[3])}

su2 = Adapter("su2_airfoil",
    backend="cli",
    command="SU2_CFD flow.cfg",
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
    setup=write_su2_config,
    parse=parse_su2_output,
    timeout=600,
    desc="SU2 Euler solver for airfoil aerodynamics",
)
```

### Using Adapters in Systems

Once created, adapters work exactly like functions:

```python
from anvil import System

# Direct call
result = water_props(P=101325, T=300)
print(result["rho"])  # density of water at 1 atm, 300 K

# In a System
pipe = System("pipe_flow")
pipe.add("P", 500e3, "Pa")
pipe.add("T", 350, "K")
pipe.add("D_pipe", 0.05, "m")
pipe.add("V_flow", 2.0, "m/s")

pipe.use(water_props)                    # get rho, mu, cp
pipe.use("reynolds_number", map={        # map adapter outputs to Re inputs
    "L_char": "D_pipe", "V": "V_flow"
})
pipe.solve().summary()
```

### Adapter File Structure

For sharing adapters, create a Python file that can be imported:

```
adapters/
    coolprop_water.py      # Adapter definition
    cantera_combustion.py
    su2_airfoil.py
```

Each file should export the adapter as a module-level variable:

```python
# coolprop_water.py
from anvil import Adapter

def _call(P, T):
    import CoolProp.CoolProp as CP
    rho = CP.PropsSI('D', 'P', P, 'T', T, 'Water')
    return {"rho": rho}

adapter = Adapter("coolprop_water", backend="python", call=_call,
    inputs={"P": {"unit": "Pa"}, "T": {"unit": "K"}},
    outputs={"rho": {"unit": "kg/m^3"}})
```

Then use it:

```python
from adapters.coolprop_water import adapter as water
system.use(water)
```

### Registering Adapters

```python
import anvil
anvil.push(water_props, domain="fluid", tags=["water", "coolprop"])

# Now available as:
anvil.R.water_properties(P=101325, T=300)
```

### Verifying Adapters

```python
anvil.check("water_properties")
# Shows inputs, outputs, test run, any issues
```

---

## Part 2: AI Agent Prompt Template for Adapter Generation

Copy the prompt below and give it to any AI agent (Claude, GPT, Gemini, etc.) along with the name of the package you want to integrate. The agent will generate ready-to-use adapter files.

---

### PROMPT (copy everything between the lines)

```
=== ANVIL FRAMEWORK ADAPTER GENERATION PROMPT ===

You are generating an Anvil Framework adapter file for the open-source
package specified below. Anvil is a Python computation framework for
engineering research. Adapters wrap external tools so they work as
native Anvil Relations inside solvable Systems.

PACKAGE TO ADAPT: [USER: replace this with your package name, e.g., "CoolProp", "Cantera", "OpenFOAM", "Pint", "SU2"]

YOUR TASK:
Generate a complete, ready-to-use Python adapter file. The user should
be able to drop this file into their project and immediately use it
with Anvil.

ANVIL ADAPTER API:
    from anvil import Adapter, Q

    adapter = Adapter(
        name="<adapter_name>",        # unique name, snake_case
        backend="python",              # "python" or "cli"
        call=<wrapper_function>,       # for python backend
        command="<cmd>",               # for cli backend
        inputs={
            "<param>": {
                "unit": "<anvil_unit>",  # e.g., "Pa", "K", "m/s", "" for dimensionless
                "desc": "<description>",
                "default": <value>,      # optional default
            },
        },
        outputs={
            "<param>": {
                "unit": "<anvil_unit>",
                "desc": "<description>",
            },
        },
        setup=<config_writer>,   # cli only: function(inputs, workdir)
        parse=<output_parser>,   # cli only: function(workdir) -> dict
        timeout=60,              # cli only: seconds
        desc="<one-line description>",
        tags=["<tag1>", "<tag2>"],
    )

ANVIL UNITS (use these exact strings):
    Pressure:     Pa, kPa, MPa, bar, atm, psi
    Temperature:  K, R
    Velocity:     m/s, km/s, ft/s
    Force:        N, kN, lbf
    Energy:       J, kJ, MJ, BTU
    Power:        W, kW, MW
    Mass:         kg, g, lb
    Length:        m, cm, mm, ft, in
    Density:      kg/m^3, g/cm^3
    Viscosity:    Pa*s, m^2/s
    Sp. heat:     J/kg/K, kJ/kg/K
    Sp. energy:   J/kg, kJ/kg
    Mass flow:    kg/s, lb/s
    Conductivity: W/m/K
    Molar:        kg/mol, g/mol, J/mol/K
    Dimensionless: "" (empty string)

RULES:
1. The wrapper function receives raw SI floats from Anvil's solver
   workspace. It must return a dict of output values.
2. For outputs with units, wrap them: Q(value, "unit").
   For dimensionless outputs, return plain floats.
3. Import the external package INSIDE the wrapper function (lazy import)
   so the adapter file can be loaded even if the package isn't installed.
4. Include clear error messages if the package is not installed.
5. Add a docstring explaining what the adapter does and what the
   external package provides.
6. Include a __main__ block that demonstrates usage and tests the adapter.
7. If the package has many possible functions, organize them as SEPARATE
   adapters (one per physical model or computation type), not one
   monolithic adapter.
8. Name adapters descriptively: "coolprop_water", "cantera_gri30_flame",
   "su2_euler_airfoil", not "adapter1".

OUTPUT FORMAT:
Generate a single Python file with this structure:

    \"\"\"
    Anvil adapter for [PACKAGE_NAME].
    
    Wraps [describe what it computes].
    Requires: pip install [package_name]
    \"\"\"
    from anvil import Adapter, Q

    def _wrapper_function(input1, input2, ...):
        try:
            import package_name
        except ImportError:
            raise ImportError(
                "[package_name] is required for this adapter.\\n"
                "  Install: pip install [package_name]"
            )
        # ... call the tool ...
        return {"output1": Q(val, "unit"), "output2": val2}

    adapter = Adapter(
        name="...",
        backend="python",
        call=_wrapper_function,
        inputs={...},
        outputs={...},
        desc="...",
        tags=[...],
    )

    # Registration (optional -- user can also do this manually)
    def register():
        import anvil
        anvil.push(adapter, domain="...", tags=[...])

    if __name__ == "__main__":
        # Demo and test
        result = adapter(input1=..., input2=...)
        print(result)

BEFORE GENERATING:
- Ask the user which specific functions/models from the package they
  want to wrap (e.g., "PropsSI for water" vs "full mixture properties")
- Ask about typical input ranges so you can set sensible defaults
- If the package is a CLI tool, ask about the config file format and
  output file format

GENERATE THE FILE NOW.
=== END PROMPT ===
```

---

### How to Use This Prompt

1. Copy the prompt above
2. Replace `[USER: replace this...]` with your package name
3. Paste into any AI agent (Claude, ChatGPT, Gemini, Copilot, etc.)
4. The agent will ask clarifying questions if needed, then generate a complete adapter file
5. Save the file as `adapters/<package_name>.py`
6. Use it:

```python
from adapters.coolprop_water import adapter as water_props
system.use(water_props)
```

Or register it globally:

```python
from adapters.coolprop_water import register
register()
# Now: anvil.R.coolprop_water(P=101325, T=300)
```

---

## Part 3: anvil.check() -- RSQ Inspection

The `check` function is the single entry point for verifying any RSQ.

### Usage

```python
import anvil

# Check a Relation
anvil.check("isentropic_ratios")

# Check a System (shows full dependency tree)
anvil.check("rocket_nozzle")

# Check a Quantity
anvil.check("g0")

# Check something that doesn't exist
anvil.check("nonexistent")  # [FAIL] with clear message

# Programmatic use (returns dict, no printing)
report = anvil.check("rocket_nozzle", verbose=False)
if report["ok"]:
    print("All good")
else:
    for issue in report["issues"]:
        print(f"  Problem: {issue}")
```

### What check() Verifies

For Relations:
- Inputs detected from function signature
- Outputs detected from return dict
- Defaults extracted
- Test run with dummy values

For Systems:
- All inputs have values (no None)
- All dependencies exist in registry
- Dependency graph is valid
- Full tree printed: inputs -> relations -> outputs
- Test solve runs successfully
- Coupled variables identified

For Quantities:
- Value, SI value, unit, dimension all present

### Report Structure

```python
report = anvil.check("rocket_nozzle", verbose=False)
report["ok"]           # bool: overall health
report["name"]         # "rocket_nozzle"
report["type"]         # "S"
report["inputs"]       # ["P0", "T0", "gamma", ...]
report["outputs"]      # ["thrust", "Isp", "M_exit", ...]
report["depends"]      # ["nozzle_area_ratio", "area_mach_supersonic", ...]
report["tree"]         # printable dependency tree string
report["issues"]       # list of problem descriptions
report["test_result"]  # dict from test solve
```

---

## Part 4: Monitoring & Visualization

### Pre-Solve Diagnostics

```python
from anvil.monitor import diagnose

msgs = diagnose(system)
for m in msgs:
    print(m)
# Example output:
#   WARNING: 'T0' = 50000 K is outside bounds (200, 5000).
#   INFO: Coupled variables detected: T_cold_out, Q_dot. Will use iterative solver.
```

### Convergence Plotting

```python
from anvil.monitor import plot_convergence, plot_variables

# Solve with monitoring enabled
result = system.solve(method="gauss_seidel", monitor=True)

# Residual vs iteration + vs wall clock
plot_convergence(system, save="convergence.png")

# Variable evolution during iteration
plot_variables(system, variables=["T_hot_out", "T_cold_out", "Q_dot"],
               save="variables.png")
```

### Sweep Charts

```python
from anvil.monitor import plot_sweep

sweep = system.sweep("P0", np.linspace(1e6, 20e6, 20))
plot_sweep(sweep, y=["thrust", "Isp"], save="sweep.png")
```

### System Dependency Graph

```python
from anvil.monitor import plot_system

plot_system(system, save="graph.png")
```

Renders inputs (green), relations (blue), and outputs (yellow) as a directed graph with arrows showing data flow.

### Watchdog (Advanced)

```python
from anvil import Watchdog

wd = Watchdog("my_system")
wd.record(iteration, workspace, residual, wallclock)
wd.check_nan(iteration, workspace)
wd.convergence_rate()     # array of successive residual ratios
wd.stalled_variables()    # variables not changing
wd.report()               # formatted diagnostic report
```
