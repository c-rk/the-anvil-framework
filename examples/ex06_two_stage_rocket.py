"""
Example 6: Multi-Stage Rocket (Composition + Tsiolkovsky)
==========================================================

Demonstrates:
    - System composition: inner nozzle System used inside outer stage System
    - Tsiolkovsky rocket equation for delta-V budgeting
    - Building a 2-stage rocket from reusable components
    - Sweeping structural mass fraction to find design space

Engineering context:
    Design a two-stage launch vehicle. Each stage uses the same
    nozzle physics but with different propellants and sizes.
    Compute total delta-V and payload fraction.
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 6: Two-Stage Launch Vehicle")
print("=" * 60)

# ==========================================
# Stage 1: Kerosene/LOX booster
# ==========================================
print(f"\n--- Stage 1: Kerosene/LOX booster ---")

stage1_nozzle = anvil.S.rocket_nozzle.copy()
stage1_nozzle.set(
    P0=15e6,         # 15 MPa chamber pressure
    T0=3400,          # K
    gamma=1.22,       # RP-1/LOX products
    R_gas=340,        # J/kg/K
    A_throat=0.05,    # m^2 (large booster)
    A_exit=0.40,      # m^2
    P_amb=101325,     # sea-level launch
)

r1 = stage1_nozzle.solve_forward()
Isp_1 = r1["Isp"].si

print(f"  Isp (sea level): {Isp_1:.1f} s")
print(f"  Thrust:          {r1['thrust'].to('kN').value:.0f} kN")
print(f"  Exit Mach:       {r1['M_exit'].si:.2f}")

# ==========================================
# Stage 2: LOX/LH2 upper stage
# ==========================================
print(f"\n--- Stage 2: LOX/LH2 upper stage ---")

stage2_nozzle = anvil.S.rocket_nozzle.copy()
stage2_nozzle.set(
    P0=8e6,           # 8 MPa
    T0=3200,           # K
    gamma=1.20,        # LOX/LH2 products
    R_gas=520,         # J/kg/K
    A_throat=0.01,     # m^2 (smaller upper stage)
    A_exit=0.12,       # m^2 (high expansion for vacuum)
    P_amb=0,           # vacuum
)

r2 = stage2_nozzle.solve_forward()
Isp_2 = r2["Isp"].si

print(f"  Isp (vacuum):    {Isp_2:.1f} s")
print(f"  Thrust:          {r2['thrust'].to('kN').value:.0f} kN")
print(f"  Exit Mach:       {r2['M_exit'].si:.2f}")

# ==========================================
# Vehicle sizing with Tsiolkovsky
# ==========================================
print(f"\n--- Vehicle sizing ---")

# Mass breakdown
m_payload   = 5000    # kg
m_struct_2  = 2000    # kg (2nd stage dry mass)
m_struct_1  = 15000   # kg (1st stage dry mass)

# Required delta-V budget
dV_gravity_drag = 1500   # m/s (gravity + drag losses)
dV_orbit        = 9400   # m/s (LEO insertion velocity)
dV_total        = dV_orbit + dV_gravity_drag

# Split: 60% stage 1, 40% stage 2 (typical)
dV_1 = 0.60 * dV_total
dV_2 = 0.40 * dV_total

print(f"  Payload:     {m_payload} kg")
print(f"  dV target:   {dV_total} m/s")
print(f"  Stage 1 dV:  {dV_1:.0f} m/s (Isp = {Isp_1:.0f} s)")
print(f"  Stage 2 dV:  {dV_2:.0f} m/s (Isp = {Isp_2:.0f} s)")

# Stage 2 propellant (Tsiolkovsky)
g0 = 9.80665
MR_2 = np.exp(dV_2 / (Isp_2 * g0))
m_dry_2 = m_payload + m_struct_2
m_prop_2 = m_dry_2 * (MR_2 - 1)
m_wet_2 = m_dry_2 + m_prop_2

print(f"\n  Stage 2:")
print(f"    Mass ratio:  {MR_2:.3f}")
print(f"    Propellant:  {m_prop_2:.0f} kg")
print(f"    Wet mass:    {m_wet_2:.0f} kg")

# Stage 1 propellant
MR_1 = np.exp(dV_1 / (Isp_1 * g0))
m_dry_1 = m_wet_2 + m_struct_1  # stage 1 carries all of stage 2
m_prop_1 = m_dry_1 * (MR_1 - 1)
m_wet_1 = m_dry_1 + m_prop_1
m_liftoff = m_wet_1

print(f"\n  Stage 1:")
print(f"    Mass ratio:  {MR_1:.3f}")
print(f"    Propellant:  {m_prop_1:.0f} kg")
print(f"    Wet mass:    {m_wet_1:.0f} kg")

print(f"\n  Vehicle totals:")
print(f"    Liftoff mass:    {m_liftoff:.0f} kg ({m_liftoff/1000:.1f} tonnes)")
print(f"    Payload fraction: {m_payload/m_liftoff:.4f} ({m_payload/m_liftoff*100:.2f}%)")
print(f"    Propellant mass: {(m_prop_1 + m_prop_2):.0f} kg")

# ==========================================
# Using Anvil Systems for the same calculation
# ==========================================
print(f"\n--- Same calculation as an Anvil System ---")

vehicle = System("two_stage_vehicle")
vehicle.add("Isp_1",      Isp_1,     "s",  desc="Stage 1 Isp")
vehicle.add("Isp_2",      Isp_2,     "s",  desc="Stage 2 Isp")
vehicle.add("dV_1",       dV_1,      "m/s")
vehicle.add("dV_2",       dV_2,      "m/s")
vehicle.add("m_payload",  m_payload, "kg")
vehicle.add("m_struct_1", m_struct_1,"kg")
vehicle.add("m_struct_2", m_struct_2,"kg")

def stage_2_sizing(dV_2, Isp_2, m_payload, m_struct_2):
    MR = np.exp(dV_2 / (Isp_2 * 9.80665))
    m_dry = m_payload + m_struct_2
    m_prop = m_dry * (MR - 1)
    return {"m_prop_2": Q(m_prop, "kg"), "m_wet_2": Q(m_dry + m_prop, "kg")}

def stage_1_sizing(dV_1, Isp_1, m_wet_2, m_struct_1):
    MR = np.exp(dV_1 / (Isp_1 * 9.80665))
    m_dry = m_wet_2 + m_struct_1
    m_prop = m_dry * (MR - 1)
    m_liftoff = m_dry + m_prop
    return {"m_prop_1": Q(m_prop, "kg"), "m_liftoff": Q(m_liftoff, "kg")}

def payload_fraction(m_payload, m_liftoff):
    return {"payload_fraction": m_payload / m_liftoff}

vehicle.use(stage_2_sizing)
vehicle.use(stage_1_sizing)
vehicle.use(payload_fraction)

result = vehicle.solve_forward()
result.summary(keys=["Isp_1", "Isp_2", "dV_1", "dV_2",
                       "m_prop_2", "m_wet_2", "m_prop_1",
                       "m_liftoff", "payload_fraction"])

# --- Sweep: payload fraction vs dV split ---
print(f"\n--- Sweep: payload fraction vs Stage 1 dV fraction ---")
dV_splits = np.linspace(0.4, 0.8, 5)
results = []
for frac in dV_splits:
    vehicle.set(dV_1=frac * dV_total, dV_2=(1 - frac) * dV_total)
    r = vehicle.solve_forward()
    pf = r["payload_fraction"].si
    results.append(pf)
    print(f"  Stage 1 = {frac:.0%} of dV  -->  payload fraction = {pf:.4f}")

best_idx = np.argmax(results)
print(f"\n  Optimal split: {dV_splits[best_idx]:.0%} / {1-dV_splits[best_idx]:.0%}")
print(f"  Best payload fraction: {results[best_idx]:.4f}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
