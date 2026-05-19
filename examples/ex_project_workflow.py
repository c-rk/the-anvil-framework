"""
Example: Custom Relations + Project Registry
=============================================

Scenario: pipe flow design — friction factor, pressure drop, pump power.
All three relations are written from scratch and managed in a project registry.

Shows:
    1. Writing your own Relations (plain functions returning dicts)
    2. Defining your own Quantities with units
    3. Building a System from those Relations
    4. Using the project registry to store work-in-progress RSQs
    5. Accessing project RSQs by name in a System
    6. Promoting a finished RSQ to the global registry
"""

import sys, os

import numpy as np
import anvil
from anvil import Q, system

# ─────────────────────────────────────────────────────────────────
# PART 1 — Define your own Relations (plain Python functions)
#
# Rules:
#   - Accept inputs as keyword arguments
#   - Return a dict
#   - Wrap dimensional outputs in Q(value, "unit") so units propagate
# ─────────────────────────────────────────────────────────────────

def friction_factor(Re, roughness_ratio=0.0):
    """
    Darcy-Weisbach friction factor.
    Laminar Re < 2300: f = 64/Re
    Turbulent Re >= 2300: Swamee-Jain explicit approximation
    roughness_ratio = epsilon/D (dimensionless)
    """
    if Re < 2300:
        f = 64.0 / Re
    else:
        # Swamee-Jain (explicit approx to Colebrook)
        numerator   = roughness_ratio / 3.7
        denominator = 5.74 / Re**0.9
        f = 0.25 / (np.log10(numerator + denominator))**2
    return {"f_darcy": f}


def pressure_drop(f_darcy, rho, V, D_pipe, L_pipe):
    """
    Darcy-Weisbach pressure drop: dP = f * (L/D) * 0.5 * rho * V^2
    """
    dP = f_darcy * (L_pipe / D_pipe) * 0.5 * rho * V**2
    return {"dP": Q(dP, "Pa")}


def pump_power(dP, V, D_pipe, eta_pump=0.75):
    """
    Hydraulic pump power: W = Q_vol * dP / eta
    Q_vol = V * pi/4 * D^2
    """
    A     = np.pi / 4 * D_pipe**2
    Q_vol = V * A
    W_hyd = Q_vol * dP          # watts if dP in Pa, Q_vol in m^3/s
    W_shaft = W_hyd / eta_pump
    return {
        "W_hydraulic": Q(W_hyd,   "W"),
        "W_shaft":     Q(W_shaft, "W"),
        "Q_vol":       Q(Q_vol,   "m^3/s"),
    }


# ─────────────────────────────────────────────────────────────────
# PART 2 — Open a project registry
#
# Creates (or opens) a local .db file in the given directory.
# Nothing goes to the global registry until you explicitly promote it.
# ─────────────────────────────────────────────────────────────────

print("=" * 60)
print("  PART 2: Project Registry")
print("=" * 60)

project_dir = os.path.join(os.path.dirname(__file__), "pipe_project")
os.makedirs(project_dir, exist_ok=True)

proj = anvil.project("pipe_flow", path=project_dir)
# → Creates: pipe_project/.anvil/project_pipe_flow.db

# Register your three relations to the project
proj.push(friction_factor,
    domain="fluid.pipe",
    description="Darcy-Weisbach friction factor (laminar + Swamee-Jain turbulent)",
    tags=["pipe", "friction", "darcy"])

proj.push(pressure_drop,
    domain="fluid.pipe",
    description="Darcy-Weisbach pressure drop along a pipe segment",
    tags=["pipe", "pressure_drop"])

proj.push(pump_power,
    domain="fluid.pipe",
    description="Hydraulic and shaft pump power from flow and pressure drop",
    tags=["pipe", "pump", "power"])

# List what's in the project
proj.list()


# ─────────────────────────────────────────────────────────────────
# PART 3 — Use project RSQs directly (no System needed)
#
# Quick sanity check on each relation before wiring them together.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 3: Direct calls to project RSQs")
print("=" * 60)

# proj.R.<name> gives you the callable Relation
r_lam = proj.R.friction_factor(Re=1000)
r_tur = proj.R.friction_factor(Re=50000, roughness_ratio=0.001)

print(f"\n  Laminar  Re=1000  : f = {r_lam['f_darcy']:.5f}  (expect 0.064)")
print(f"  Turbulent Re=50000 : f = {r_tur['f_darcy']:.5f}")

r_dp = proj.R.pressure_drop(
    f_darcy=r_tur["f_darcy"],
    rho=998.2, V=2.0, D_pipe=0.05, L_pipe=10.0
)
print(f"  Pressure drop: {r_dp['dP']}")


# ─────────────────────────────────────────────────────────────────
# PART 4 — Build a System using project RSQs
#
# Use proj.R.<name> to pull a relation from the project into a System.
# Alternatively use the string name: sys.use("friction_factor")
# works the same once the RSQ is in the project registry.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 4: System built from own Relations")
print("=" * 60)

# --- Define inputs with units ---
pipe_sys = system("water_pipe")

pipe_sys.add("rho",            998.2,  "kg/m^3",  desc="Water density")
pipe_sys.add("V",                2.0,  "m/s",     desc="Mean flow velocity")
pipe_sys.add("D_pipe",          0.05,  "m",       desc="Pipe inner diameter")
pipe_sys.add("L_pipe",          10.0,  "m",       desc="Pipe length")
pipe_sys.add("roughness_ratio", 1e-4,             desc="Relative roughness eps/D")
pipe_sys.add("eta_pump",        0.75,             desc="Pump efficiency")

# Add Reynolds number from the built-in registry RSQ
pipe_sys.add("mu",            1.002e-3, "Pa*s",   desc="Dynamic viscosity (water)")
pipe_sys.use("reynolds_number",
    map={"L_char": "D_pipe"})    # map the 'L_char' input to our 'D_pipe'

# Add our own relations from the project.
#
# IMPORTANT: sys.use("name") only searches the GLOBAL registry.
# Project RSQs must be passed as objects via proj.R.<name>.
pipe_sys.use(proj.R.friction_factor)
pipe_sys.use(proj.R.pressure_drop)
pipe_sys.use(proj.R.pump_power)

# Solve — acyclic (feed-forward), so forward pass
result = pipe_sys.solve_forward()
result.summary()

# --- Unit conversions on results ---
print("\n  Key results:")
print(f"    Re         = {result['Re'].value:.0f}  (turbulent: {'yes' if result['Re'].si > 2300 else 'no'})")
print(f"    f_darcy    = {result['f_darcy'].value:.5f}")
print(f"    dP         = {result['dP'].to('kPa').value:.3f} kPa")
print(f"    W_shaft    = {result['W_shaft'].to('kW').value:.4f} kW")
print(f"    Q_vol      = {result['Q_vol'].value:.6f} m^3/s"
      f"  ({result['Q_vol'].si * 1000:.2f} L/s)")


# ─────────────────────────────────────────────────────────────────
# PART 5 — Parametric sweep using the system
#
# Vary flow velocity; observe friction factor, pressure drop, pump power.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 5: Velocity sweep")
print("=" * 60)

sweep = pipe_sys.sweep("V", np.linspace(0.5, 4.0, 8), parallel=2)
sweep.summary(outputs=["Re", "f_darcy", "dP", "W_shaft"])


# ─────────────────────────────────────────────────────────────────
# PART 6 — Promote to global registry
#
# Once your relations are validated and producing correct results,
# promote them from the project store to the global registry.
# They then become available to any script via anvil.R.<name>.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 6: Promote to global registry")
print("=" * 60)

proj.promote("friction_factor", overwrite=True)
proj.promote("pressure_drop",   overwrite=True)
proj.promote("pump_power",      overwrite=True)

# Verify they're now in global registry
print("\n  Searching global registry for 'pipe'...")
anvil.registry.search("pipe")

# Access via global namespace — exactly like any built-in RSQ
r_check = anvil.R.friction_factor(Re=1000)
print(f"\n  anvil.R.friction_factor(Re=1000) -> f = {r_check['f_darcy']:.4f}")


# ─────────────────────────────────────────────────────────────────
# CLEANUP (optional — remove promoted RSQs from global for clean demo)
# ─────────────────────────────────────────────────────────────────

for name in ("friction_factor", "pressure_drop", "pump_power"):
    anvil.registry.remove(name)

import shutil
shutil.rmtree(project_dir, ignore_errors=True)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
