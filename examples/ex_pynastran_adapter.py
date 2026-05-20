"""
Example: pyNASTRAN / NASTRAN FEM Adapter
=========================================
Demonstrates nastran_linear_static and nastran_normal_modes.
Mock mode (Euler-Bernoulli + analytical frequencies) runs without NASTRAN.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.pynastran_fem import (
    nastran_linear_static, nastran_normal_modes, register
)

# ── Linear static ─────────────────────────────────────────────────────────────
print("=== NASTRAN SOL 101: linear static (cantilever beam) ===")
r = nastran_linear_static(
    bdf_path="no_model.bdf",   # won't exist → mock mode
    load_case_id=1,
    E_fallback=200e9,          # Pa (steel)
    I_fallback=4.167e-6,       # m^4  (50mm × 50mm square: I = b⁴/12)
    L_fallback=1.0,            # m
    F_fallback=1000.0,         # N
)
print(f"  Max displacement = {r['max_displacement']}")
print(f"  Max stress (v.M.) = {r['max_stress']}")
print(f"  source: {r['source']}")
# Check: δ = FL³/(3EI)
delta_check = 1000 * 1.0**3 / (3 * 200e9 * 4.167e-6)
print(f"  Analytical δ     = {delta_check*1000:.3f} mm")

# ── Normal modes ─────────────────────────────────────────────────────────────
print("\n=== NASTRAN SOL 103: normal modes (cantilever beam, 6 modes) ===")
r2 = nastran_normal_modes(
    bdf_path="no_model.bdf",
    n_modes=6,
    E_fallback=200e9,
    I_fallback=4.167e-6,
    L_fallback=1.0,
    rho_fallback=7800.0,
    A_fallback=0.0025,   # 50mm × 50mm
)
print(f"  n_modes = {r2['n_modes']}")
print(f"  f1      = {r2['f1']}  (1st bending)")
print(f"  f2      = {r2['f2']}  (2nd bending)")
print(f"  All frequencies:")
for i, f in enumerate(r2['frequencies'], 1):
    fq = float(f.si) if hasattr(f, "si") else float(f)
    print(f"    Mode {i}: {fq:.2f} Hz")
print(f"  source: {r2['source']}")

# ── Material sweep: freq vs Young's modulus ──────────────────────────────────
print("\n=== 1st natural frequency vs Young's modulus ===")
sys_ = anvil.system("nastran_E_sweep")
sys_.add("bdf_path",   "no_model.bdf")
sys_.add("n_modes",    6)
sys_.add("E_fallback", 200e9)
sys_.add("I_fallback", 4.167e-6)
sys_.add("L_fallback", 1.0)
sys_.add("rho_fallback", 7800.0)
sys_.add("A_fallback", 0.0025)
sys_.use(nastran_normal_modes)

E_vals  = [70e9, 120e9, 200e9, 300e9, 400e9]
labels  = ["Al (70)", "Ti (120)", "Steel (200)", "WC (300)", "Diamond (400)"]
sweep   = sys_.sweep("E_fallback", E_vals)
print(f"  {'Material':>15}  {'E [GPa]':>9}  {'f1 [Hz]':>9}")
for i, (mat, Eval) in enumerate(zip(labels, E_vals)):
    row = sweep.table.iloc[i]
    f1  = row.get("f1", None)
    if f1 is None:
        continue
    f1_hz = float(f1.si) if hasattr(f1, "si") else float(f1)
    print(f"  {mat:>15}  {Eval/1e9:9.0f}  {f1_hz:9.2f}")
print("  (f1 ∝ √E: doubling E → 1.41× higher frequency)")

# ── Geometry sensitivity: freq vs beam length ──────────────────────────────────
print("\n=== 1st natural frequency vs beam length (steel beam) ===")
sys2 = anvil.system("nastran_L_sweep")
sys2.add("bdf_path",    "no_model.bdf")
sys2.add("n_modes",     6)
sys2.add("E_fallback",  200e9)
sys2.add("I_fallback",  4.167e-6)
sys2.add("L_fallback",  1.0)
sys2.add("rho_fallback", 7800.0)
sys2.add("A_fallback",  0.0025)
sys2.use(nastran_normal_modes)

L_vals = np.linspace(0.5, 3.0, 6)
sweep2 = sys2.sweep("L_fallback", L_vals)
print(f"  {'L [m]':>7}  {'f1 [Hz]':>9}")
for i in range(len(L_vals)):
    row = sweep2.table.iloc[i]
    f1  = row.get("f1", None)
    if f1 is None:
        continue
    f1_hz = float(f1.si) if hasattr(f1, "si") else float(f1)
    print(f"  {L_vals[i]:7.2f}  {f1_hz:9.2f}")
print("  (f1 ∝ 1/L²: doubling length → 4× lower frequency)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: nastran_linear_static, nastran_normal_modes → domain fem.nastran")
