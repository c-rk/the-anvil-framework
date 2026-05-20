"""
Example: XFOIL 2D Airfoil Adapter
===================================
Demonstrates xfoil_polar and xfoil_alpha_sweep.
Mock mode (thin-airfoil + Prandtl-Glauert) is used when XFOIL is not on PATH.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.xfoil_airfoil import xfoil_polar, xfoil_alpha_sweep, register

# ── Single operating point ────────────────────────────────────────────────────
print("=== Single operating point (AoA = 4°, Re = 1e6) ===")
r = xfoil_polar(AoA_deg=4.0, Re=1e6, Mach=0.1, n_panels=160)
print(f"  CL   = {r['CL']:.4f}")
print(f"  CD   = {r['CD']:.5f}")
print(f"  CM   = {r['CM']:.4f}")
print(f"  L/D  = {r['CL']/r['CD']:.1f}")
print(f"  source: {r['source']}")

# ── Polar sweep ───────────────────────────────────────────────────────────────
print("\n=== Alpha sweep (-4° to 12°, Re = 1.5e6) ===")
r = xfoil_alpha_sweep(
    alpha_start=-4.0, alpha_end=12.0, alpha_step=2.0,
    Re=1.5e6, Mach=0.15,
)
print(f"  Points computed: {r['n_points']}")
print(f"  CL range: [{min(r['CL_list']):.3f}, {max(r['CL_list']):.3f}]")
print(f"  Best L/D = {r['LD_max']:.1f}  at AoA = {r['AoA_LD_max']:.1f}°")
print(f"  CL_max   = {r['CL_max']:.3f}")
print(f"  source: {r['source']}")

# ── Sweep over Mach with Anvil System ────────────────────────────────────────
print("\n=== Compressibility effect: CL vs Mach (AoA=5°) ===")
sys_ = anvil.system("xfoil_mach_study")
sys_.add("AoA_deg", 5.0)
sys_.add("Re",     2e6)
sys_.add("Mach",   0.0)   # placeholder
sys_.add("n_panels", 160)
sys_.use(xfoil_polar)

sweep = sys_.sweep("Mach", np.linspace(0.05, 0.70, 8))
machs  = sweep.table["Mach"].tolist()
cls    = sweep.table["CL"].tolist()
print(f"  {'Mach':>6}  {'CL':>7}")
for m, cl in zip(machs, cls):
    print(f"  {m:6.2f}  {cl:7.4f}")
print("  (CL rises with Mach due to Prandtl-Glauert β = √(1-M²) in denominator)")

# ── Register in project ───────────────────────────────────────────────────────
print("\n=== Register in project ===")
proj = anvil.project("airfoil_study", path="./work_xfoil")
register()
print("  Global registry: xfoil_polar, xfoil_alpha_sweep  → domain aero.xfoil")
