"""
Example: SU2 CFD Adapter
=========================
Demonstrates su2_euler and su2_rans.
Mock mode (Prandtl-Glauert + flat-plate BL) runs without SU2 installed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.su2_aero import su2_euler, su2_rans, register

# ── Euler (inviscid) ─────────────────────────────────────────────────────────
print("=== SU2 Euler: inviscid airfoil (M=0.3, AoA=4°) ===")
r = su2_euler(
    cfg_template="no_template.cfg",   # won't exist → mock mode
    mesh="no_mesh.su2",
    Mach=0.3, AoA_deg=4.0,
)
print(f"  CL     = {r['CL']:.4f}")
print(f"  CD     = {r['CD']:.5f}  (induced + wave; zero friction in Euler)")
print(f"  CM     = {r['CM']:.4f}")
print(f"  source : {r['source']}")

# ── RANS (viscous) ───────────────────────────────────────────────────────────
print("\n=== SU2 RANS: viscous airfoil (M=0.3, AoA=4°, Re=3e6) ===")
r2 = su2_rans(
    cfg_template="no_template.cfg",
    mesh="no_mesh.su2",
    Mach=0.3, AoA_deg=4.0, Reynolds=3e6,
)
print(f"  CL     = {r2['CL']:.4f}")
print(f"  CD     = {r2['CD']:.5f}  (pressure + friction)")
print(f"  CM     = {r2['CM']:.4f}")
print(f"  Re     = {float(r2['Re']):.2e}")
print(f"  source : {r2['source']}")
print(f"  ΔCD (friction) = {r2['CD'] - r['CD']:.5f}")

# ── Mach sweep: wave drag onset ───────────────────────────────────────────────
print("\n=== Wave drag onset: CD vs Mach (AoA=2°, inviscid) ===")
sys_ = anvil.system("su2_mach_sweep")
sys_.add("cfg_template", "no_template.cfg")
sys_.add("mesh",         "no_mesh.su2")
sys_.add("AoA_deg",      2.0)
sys_.add("sideslip_deg", 0.0)
sys_.add("alpha0_deg",   0.0)
sys_.add("Mach",         0.3)
sys_.use(su2_euler)

machs = np.linspace(0.3, 0.95, 10)
sweep = sys_.sweep("Mach", machs)

print(f"  {'Mach':>6}  {'CL':>7}  {'CD':>8}")
for i in range(len(machs)):
    row = sweep.table.iloc[i]
    print(f"  {row['Mach']:.3f}  {row['CL']:7.4f}  {row['CD']:8.5f}")
print("  (CD rises sharply above M=0.8 due to wave drag: 0.01·(M-0.8)^1.5)")

# ── Reynolds sweep: viscous drag scaling ─────────────────────────────────────
print("\n=== Viscous drag vs Reynolds number (M=0.3, AoA=4°) ===")
sys2 = anvil.system("su2_re_sweep")
sys2.add("cfg_template", "no_template.cfg")
sys2.add("mesh",         "no_mesh.su2")
sys2.add("Mach",         0.3)
sys2.add("AoA_deg",      4.0)
sys2.add("sideslip_deg", 0.0)
sys2.add("alpha0_deg",   0.0)
sys2.add("Reynolds",     1e6)
sys2.use(su2_rans)

Re_vals = np.logspace(5, 7, 6)
sweep2  = sys2.sweep("Reynolds", Re_vals)
print(f"  {'Re':>10}  {'CD_total':>10}")
for i in range(len(Re_vals)):
    row = sweep2.table.iloc[i]
    print(f"  {row['Reynolds']:10.2e}  {row['CD']:10.6f}")
print("  (friction CD ∝ Re^-0.258 via Prandtl-Schlichting flat-plate formula)")

# ── Register ─────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: su2_euler, su2_rans → domain cfd.su2")
