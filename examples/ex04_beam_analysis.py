"""
Example 4: Structural Beam Analysis
====================================

Demonstrates:
    - Using built-in structures RSQs
    - Building custom Relations from scratch
    - Bounds checking and diagnostics
    - Comparing analytical solutions

Engineering context:
    Analyze a cantilever beam and a simply-supported beam under load.
    Check safety margins against yield stress. Sweep beam length
    to find the maximum span before yield.
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System
from anvil.monitor import diagnose

print("=" * 60)
print("  Example 4: Structural Beam Analysis")
print("=" * 60)

# --- Material: Aluminum 6061-T6 ---
E_al     = 68.9e9    # Pa (Young's modulus)
sigma_y  = 276e6     # Pa (yield strength)
rho_al   = 2700      # kg/m^3

# --- Cross section: rectangular beam 50mm wide x 100mm tall ---
b = 0.050   # width, m
h = 0.100   # height, m
A = b * h   # cross-sectional area
I = b * h**3 / 12  # second moment of area

print(f"\n[1] Beam properties:")
print(f"  Material:  Al 6061-T6 (E = {E_al/1e9:.1f} GPa, sigma_y = {sigma_y/1e6:.0f} MPa)")
print(f"  Section:   {b*1000:.0f} mm x {h*1000:.0f} mm rectangular")
print(f"  Area:      {A*1e4:.2f} cm^2")
print(f"  I:         {I*1e8:.4f} cm^4")

# ==========================================
# Part A: Cantilever Beam with Tip Load
# ==========================================
print(f"\n{'='*40}")
print(f"  Part A: Cantilever Beam")
print(f"{'='*40}")

F_tip = 5000  # N
L = 2.0       # m

result = anvil.R.beam_deflection_cantilever(
    F_tip=F_tip, L_beam=L, E=E_al, I_moment=I
)

deflection = result["deflection"].si
max_moment = result["max_moment"].si
max_stress = max_moment * (h/2) / I  # sigma = M*c/I

print(f"\n  Load:       {F_tip} N at tip")
print(f"  Length:     {L} m")
print(f"  Deflection: {deflection*1000:.2f} mm")
print(f"  Max moment: {max_moment:.0f} N*m")
print(f"  Max stress: {max_stress/1e6:.1f} MPa")
print(f"  Safety margin: {sigma_y / max_stress:.2f}x")

# --- Sweep: deflection vs beam length ---
print(f"\n  Sweep: deflection vs length...")

cant = System("cantilever")
cant.add("F_tip",    F_tip, "N")
cant.add("L_beam",   L,     "m")
cant.add("E",        E_al,  "Pa")
cant.add("I_moment", I,     "m")     # m^4 but Anvil tracks dims automatically
cant.use("beam_deflection_cantilever")

sweep = cant.sweep("L_beam", np.linspace(0.5, 4.0, 8))
sweep.summary(outputs=["deflection", "max_moment"])

# ==========================================
# Part B: Simply Supported Beam Under Uniform Load
# ==========================================
print(f"\n{'='*40}")
print(f"  Part B: Simply Supported Beam")
print(f"{'='*40}")

w_load = 2000  # N/m (distributed load)
L_ss = 3.0     # m

result_ss = anvil.R.beam_deflection_simply_supported(
    w_load=w_load, L_beam=L_ss, E=E_al, I_moment=I
)

print(f"\n  Load:       {w_load} N/m uniform")
print(f"  Length:     {L_ss} m")
print(f"  Max deflection: {result_ss['deflection'].si*1000:.2f} mm")
print(f"  Max moment:     {result_ss['max_moment'].si:.0f} N*m")

# ==========================================
# Part C: Euler Buckling
# ==========================================
print(f"\n{'='*40}")
print(f"  Part C: Column Buckling")
print(f"{'='*40}")

# Fixed-free column (K=2, so L_eff = 2*L)
L_col = 1.5  # m
L_eff = 2.0 * L_col  # fixed-free end condition

result_buck = anvil.R.buckling_euler(E=E_al, I_moment=I, L_eff=L_eff)
P_cr = result_buck["P_critical"].si

print(f"\n  Column length:      {L_col} m (fixed-free, K=2)")
print(f"  Effective length:   {L_eff} m")
print(f"  Critical load:      {P_cr/1000:.1f} kN")
print(f"  Safety factor at 50 kN: {P_cr / 50000:.2f}x")

# ==========================================
# Part D: Pressure Vessel
# ==========================================
print(f"\n{'='*40}")
print(f"  Part D: Pressure Vessel")
print(f"{'='*40}")

result_pv = anvil.R.thin_wall_hoop_stress(
    P_internal=5e6, r_inner=0.3, t_wall=0.005
)

print(f"\n  Internal pressure: 5 MPa")
print(f"  Radius: 300 mm, Wall: 5 mm")
print(f"  Hoop stress:   {result_pv['sigma_hoop'].si/1e6:.0f} MPa")
print(f"  Axial stress:  {result_pv['sigma_axial'].si/1e6:.0f} MPa")
print(f"  Safety (hoop): {sigma_y / result_pv['sigma_hoop'].si:.2f}x")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
