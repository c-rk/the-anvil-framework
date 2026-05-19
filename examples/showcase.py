"""
Anvil v0.3 Showcase
====================

Demonstrates the full RSQ workflow:
    1. Browse the built-in registry
    2. Call Relations directly
    3. Load a pre-built System with defaults
    4. Override with .set() — no redundant .add()
    5. Solve and sweep
    6. Compose systems
    7. Register your own RSQs
"""

import os
import sys

import numpy as np


import anvil
from anvil import Q, System

print("=" * 60)
print("  Anvil v0.3 Showcase")
print("=" * 60)

# ─────────────────────────────────────────────────
# 1. Browse what's available
# ─────────────────────────────────────────────────

print("\n--- What's in the registry? ---")
anvil.registry.list()

# ─────────────────────────────────────────────────
# 2. Search for something specific
# ─────────────────────────────────────────────────

print("\n--- Search: 'shock' ---")
anvil.registry.search("shock")

print("\n--- Search: 'thrust' ---")
anvil.registry.search("thrust")

# ─────────────────────────────────────────────────
# 3. Use a Relation directly from the registry
# ─────────────────────────────────────────────────

print("\n--- Call isentropic_ratios directly ---")
result = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
print(f"  M = 2.0, gamma = 1.4")
print(f"  T0/T   = {result['T0_T']:.4f}")
print(f"  P0/P   = {result['P0_P']:.4f}")
print(f"  rho0/rho = {result['rho0_rho']:.4f}")

print("\n--- Normal shock at M=3 ---")
shock = anvil.R.normal_shock(M1=3.0, gamma=1.4)
print(f"  M1 = 3.0")
print(f"  M2     = {shock['M2']:.4f}")
print(f"  P2/P1  = {shock['P2_P1']:.4f}")
print(f"  T2/T1  = {shock['T2_T1']:.4f}")
print(f"  P02/P01 = {shock['P02_P01']:.4f}")

# ─────────────────────────────────────────────────
# 4. Load a pre-built System — no .add() needed
# ─────────────────────────────────────────────────

print("\n--- Load the rocket nozzle system ---")
nozzle = anvil.S.rocket_nozzle
print(nozzle.info())

# Solve with defaults
print("\n--- Solve with defaults ---")
nozzle.solve().summary()

# ─────────────────────────────────────────────────
# 5. Override with .set() — clean, no re-declaration
# ─────────────────────────────────────────────────

print("\n--- Override chamber pressure and solve again ---")
nozzle.set(P0=10e6, T0=3200)
nozzle.solve().summary()

# Override with different unit system
print("\n--- Override with imperial units ---")
nozzle.set(P0=Q(1500, "psi"))
nozzle.solve().summary()

# ─────────────────────────────────────────────────
# 6. Parametric sweep
# ─────────────────────────────────────────────────

print("\n--- Sweep: thrust vs chamber pressure ---")
nozzle.set(P0=6.9e6)  # reset to baseline
sweep = nozzle.sweep("P0", np.linspace(1e6, 20e6, 10))
sweep.summary(outputs=["M_exit", "V_exit", "mdot", "thrust", "Isp"])

# ─────────────────────────────────────────────────
# 7. Compose: nozzle inside a bigger system
# ─────────────────────────────────────────────────

print("\n--- Composition: nozzle + custom delta-V calc ---")


# Define a custom Relation
def delta_v(Isp, mass_ratio):
    """Tsiolkovsky rocket equation: dV = Isp * g0 * ln(mass_ratio)"""
    import numpy as np

    dv = Isp * 9.80665 * np.log(mass_ratio)
    return {"delta_v": Q(dv, "m/s")}


# Build a stage system — use() with a System inherits its defaults
# Get a fresh nozzle from the registry
from anvil.registry.loader import load_rsq

fresh_nozzle = load_rsq(
    anvil.registry._get_store().get("rocket_nozzle"), anvil.registry._get_store()
)

stage = System("rocket_stage")
stage.use(fresh_nozzle)  # inherits all 7 nozzle defaults
stage.add("mass_ratio", 4.0, desc="Initial/final mass ratio")
stage.use(delta_v)

# Solve
stage.solve().summary()

# ─────────────────────────────────────────────────
# 8. Register your own RSQ
# ─────────────────────────────────────────────────

print("\n--- Register a custom Relation ---")


def oblique_shock_angle(M, theta_deg, gamma=1.4):
    """Find weak shock angle beta for given deflection theta."""
    import numpy as np

    from anvil import solvers

    theta = np.radians(theta_deg)
    mu = np.arcsin(1.0 / M)  # Mach angle

    def residual(beta_deg):
        b = np.radians(beta_deg)
        num = M**2 * np.sin(b) ** 2 - 1
        den = M**2 * (gamma + np.cos(2 * b)) + 2
        return np.tan(theta) - 2 * (1 / np.tan(b)) * num / den

    # Initial guess: midpoint between Mach angle and 60 degrees
    x0 = np.degrees(mu) + (60 - np.degrees(mu)) * 0.4
    beta = solvers.find_root(residual, x0=x0, method="newton")
    return {"beta_deg": beta, "beta_rad": np.radians(beta)}


anvil.push(
    oblique_shock_angle,
    domain="aero.compressible",
    tags=["shock", "oblique", "compressible"],
    description="Oblique shock wave angle from deflection angle and Mach",
)

# Now use it from the registry
print("\n--- Use the newly registered Relation ---")
result = anvil.R.oblique_shock_angle(M=3.0, theta_deg=20.0)
print(f"  M=3.0, theta=20 deg")
print(f"  beta = {result['beta_deg']:.2f} deg")

# ─────────────────────────────────────────────────
# 9. Unit conversions on results
# ─────────────────────────────────────────────────

print("\n--- Unit conversions ---")
nozzle.set(P0=6.9e6)
r = nozzle.solve()

F = r["thrust"]
print(f"  Thrust:  {F}  →  {F.to('kN')}  →  {F.to('lbf')}")

T = r["T_exit"]
print(f"  T_exit:  {T}  →  {T.to('R')}")

V = r["V_exit"]
print(f"  V_exit:  {V}  →  {V.to('ft/s')}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
