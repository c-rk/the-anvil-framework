"""
Example: OpenFOAM CFD Adapter
==============================
Demonstrates openfoam_incompressible and openfoam_compressible.
Mock mode (lifting-line + Küchemann wave drag) runs without OpenFOAM installed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.openfoam_cfd import (
    openfoam_incompressible, openfoam_compressible, register
)

# ── Incompressible: low-speed airfoil ────────────────────────────────────────
print("=== simpleFoam: incompressible airfoil (AoA=5°, U=50 m/s) ===")
r = openfoam_incompressible(
    case_path="./no_case",    # won't exist → mock mode
    U_inf=50.0,
    alpha_deg=5.0,
    rho=1.225, nu=1.5e-5,
    L_ref=1.0, A_ref=1.0,
)
print(f"  CL     = {r['CL']:.4f}")
print(f"  CD     = {r['CD']:.5f}")
print(f"  F_lift = {r['F_lift']}")
print(f"  F_drag = {r['F_drag']}")
print(f"  Re     = {float(r['Re']):.2e}")
print(f"  source : {r['source']}")

# ── Compressible: transonic ────────────────────────────────────────────────
print("\n=== rhoSimpleFoam: transonic airfoil (U=272 m/s, M≈0.8) ===")
r2 = openfoam_compressible(
    case_path="./no_case",
    U_inf=272.0,
    alpha_deg=3.0,
    p_inf=101325.0, T_inf=288.15,
)
print(f"  CL     = {r2['CL']:.4f}")
print(f"  CD     = {r2['CD']:.5f}")
print(f"  Mach   = {float(r2['Mach']):.3f}")
print(f"  F_lift = {r2['F_lift']}")
print(f"  source : {r2['source']}")

# ── Polar sweep: CL/CD vs angle of attack ────────────────────────────────────
print("\n=== Polar: CL/CD vs AoA (U=30 m/s, rho=1.225) ===")
sys_ = anvil.system("foam_polar")
sys_.add("case_path", "./no_case")
sys_.add("U_inf",     30.0)
sys_.add("rho",       1.225)
sys_.add("nu",        1.5e-5)
sys_.add("L_ref",     1.0)
sys_.add("A_ref",     1.0)
sys_.add("n_cores",   1)
sys_.add("solver",    "simpleFoam")
sys_.add("alpha_deg", 0.0)
sys_.use(openfoam_incompressible)

alphas = np.linspace(-4, 12, 9)
sweep  = sys_.sweep("alpha_deg", alphas)

print(f"  {'AoA':>6}  {'CL':>7}  {'CD':>8}  {'L/D':>7}")
for i in range(len(alphas)):
    row = sweep.table.iloc[i]
    ld  = row["CL"] / row["CD"] if row["CD"] != 0 else float("inf")
    print(f"  {row['alpha_deg']:6.1f}  {row['CL']:7.4f}  {row['CD']:8.5f}  {ld:7.1f}")
print("  (CD minimum near AoA=0; L/D max near AoA=4-6°)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: openfoam_incompressible, openfoam_compressible → domain cfd.openfoam")
