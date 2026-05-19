"""
Example 4: Structural Beam Analysis
====================================

Demonstrates:
    - Using built-in structures RSQs
    - Working with physical quantities (Q objects carry units)
    - Beam deflection, buckling, and pressure vessel analysis
    - Sweep over beam length to find safe working range

Engineering context:
    Analyze aluminum beams under various loading conditions.
    All physical quantities declared as Q objects -- units propagate
    automatically through calculations and appear in output.
"""

import numpy as np
import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 4: Structural Beam Analysis")
print("=" * 60)

# Material: Aluminum 6061-T6
E        = Q(68.9e9,  "Pa")      # Young's modulus
sigma_y  = Q(276e6,   "Pa")      # yield strength
rho      = Q(2700,    "kg/m^3")  # density

# Cross section: 50 mm x 100 mm rectangular
b = Q(0.050, "m")
h = Q(0.100, "m")
A = b * h                        # m^2
I = b * h**3 / 12                # m^4

print(f"\n[1] Beam properties:")
print(f"  E        = {E.to('GPa')}")
print(f"  sigma_y  = {sigma_y.to('MPa')}")
print(f"  section  = {b.to('mm')} x {h.to('mm')}")
print(f"  Area     = {A}")
print(f"  I        = {I}")


# ── Part A: Cantilever under tip load ────────────────────────────────────────
print(f"\n[A] Cantilever beam, 5 kN tip load:")

F = Q(5000, "N")
L = Q(2.0,  "m")

r = anvil.R.beam_deflection_cantilever(
    F_tip=F.si, L_beam=L.si, E=E.si, I_moment=I.si
)
max_stress = r["max_moment"] * (h / 2) / I

print(f"  deflection  = {r['deflection'].to('mm')}")
print(f"  max moment  = {r['max_moment']}")
print(f"  max stress  = {max_stress.to('MPa')}")
print(f"  safety vs yield = {(sigma_y / max_stress):.2f}x")

# Sweep beam length
print(f"\n  Sweep: deflection vs length (0.5 to 4 m):")
cant = System("cantilever")
cant.add("F_tip",    F.si,  "N")
cant.add("L_beam",   L.si,  "m")
cant.add("E",        E.si,  "Pa")
cant.add("I_moment", I.si,  "m^4")
cant.use("beam_deflection_cantilever")
cant.sweep("L_beam", np.linspace(0.5, 4.0, 8)).summary(
    outputs=["deflection", "max_moment"])


# ── Part B: Simply-supported under uniform load ───────────────────────────────
print(f"\n[B] Simply-supported beam, 2 kN/m uniform load:")

w = Q(2000, "N/m")
L_ss = Q(3.0, "m")

r_ss = anvil.R.beam_deflection_simply_supported(
    w_load=w.si, L_beam=L_ss.si, E=E.si, I_moment=I.si
)
print(f"  max deflection = {r_ss['deflection'].to('mm')}")
print(f"  max moment     = {r_ss['max_moment']}")


# ── Part C: Euler column buckling ─────────────────────────────────────────────
print(f"\n[C] Column buckling (fixed-free, K=2):")

L_col = Q(1.5, "m")
L_eff = Q(2.0 * L_col.si, "m")   # effective length for fixed-free

r_buck = anvil.R.buckling_euler(E=E.si, I_moment=I.si, L_eff=L_eff.si)
print(f"  critical load = {r_buck['P_critical'].to('kN')}")
print(f"  safety at 50 kN = {r_buck['P_critical'] / Q(50e3,'N'):.2f}x")


# ── Part D: Thin-wall pressure vessel ─────────────────────────────────────────
print(f"\n[D] Thin-wall pressure vessel:")

r_pv = anvil.R.thin_wall_hoop_stress(
    P_internal=Q(5e6,"Pa").si, r_inner=Q(0.3,"m").si, t_wall=Q(0.005,"m").si
)
print(f"  hoop stress  = {r_pv['sigma_hoop'].to('MPa')}")
print(f"  axial stress = {r_pv['sigma_axial'].to('MPa')}")
print(f"  safety (yield / hoop) = {sigma_y / r_pv['sigma_hoop']:.2f}x")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
