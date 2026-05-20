"""
Example: FEniCSx FEM Adapter
==============================
Demonstrates fenics_linear_elasticity and fenics_heat_conduction.
Mock mode (Euler-Bernoulli beam, 1D Fourier) runs without FEniCSx installed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.fenics_fem import (
    fenics_linear_elasticity, fenics_heat_conduction, register
)

# ── Linear elasticity: cantilever box ────────────────────────────────────────
print("=== FEniCSx linear elasticity: cantilever box ===")
r = fenics_linear_elasticity(
    E=200e9, nu=0.3,
    Lx=1.0, Ly=0.05, Lz=0.05,
    F_distributed=1e4,    # N/m^2 on top face
    nx=20, ny=4, nz=4,
)
print(f"  Max displacement = {r['max_displacement']}")
print(f"  Max von Mises    = {r['max_von_mises']}")
print(f"  source: {r['source']}")
# Analytical check: δ = wL⁴/(8EI)
import math
w = 1e4 * 0.05
I = 0.05 * 0.05**3 / 12
delta_analytical = w * 1.0**4 / (8 * 200e9 * I)
print(f"  Analytical δ     = {delta_analytical*1000:.4f} mm  (Euler-Bernoulli check)")

# ── Geometry sensitivity: deflection vs length ───────────────────────────────
print("\n=== Deflection vs beam length (E=200GPa, Ly=Lz=5cm, F=10kPa) ===")
sys_ = anvil.system("fenics_length_sweep")
sys_.add("E",            200e9)
sys_.add("nu",           0.3)
sys_.add("Lx",           1.0)
sys_.add("Ly",           0.05)
sys_.add("Lz",           0.05)
sys_.add("F_distributed", 1e4)
sys_.add("nx",           20)
sys_.add("ny",           4)
sys_.add("nz",           4)
sys_.use(fenics_linear_elasticity)

Lx_vals = np.linspace(0.5, 2.0, 6)
sweep   = sys_.sweep("Lx", Lx_vals)
print(f"  {'Lx [m]':>7}  {'δ_max [mm]':>12}  {'σ_vm [MPa]':>12}")
for i in range(len(Lx_vals)):
    row  = sweep.table.iloc[i]
    d = row["max_displacement"]
    s = row["max_von_mises"]
    d_mm  = float(d.si) * 1000 if hasattr(d, "si") else float(d) * 1000
    s_mpa = float(s.si) / 1e6  if hasattr(s, "si") else float(s) / 1e6
    print(f"  {Lx_vals[i]:7.2f}  {d_mm:12.3f}  {s_mpa:12.2f}")
print("  (δ ∝ L⁴, σ ∝ L²: doubling length → 16× more deflection, 4× more stress)")

# ── Heat conduction ────────────────────────────────────────────────────────────
print("\n=== FEniCSx heat conduction: aluminium rod ===")
r2 = fenics_heat_conduction(
    k=205.0,       # W/m/K  (aluminium)
    Lx=0.5,        # m
    Ly=0.02, Lz=0.02,
    T_left=600.0,  # K
    T_right=300.0, # K
    Q_vol=0.0,
    nx=20, ny=5, nz=5,
)
print(f"  T_max     = {r2['T_max']}")
print(f"  Heat flux = {r2['heat_flux']}")
print(f"  source: {r2['source']}")
# 1D Fourier check: Q = k·A·ΔT/L
A = 0.02 * 0.02
Q_analytical = 205.0 * A * (600.0 - 300.0) / 0.5
print(f"  Analytical Q = {Q_analytical:.2f} W")

# ── Thermal sensitivity: conductivity sweep ────────────────────────────────────
print("\n=== Heat flux vs thermal conductivity (ΔT=300K, L=0.5m) ===")
sys2 = anvil.system("fenics_k_sweep")
sys2.add("k",       205.0)
sys2.add("Lx",      0.5)
sys2.add("Ly",      0.02)
sys2.add("Lz",      0.02)
sys2.add("T_left",  600.0)
sys2.add("T_right", 300.0)
sys2.add("Q_vol",   0.0)
sys2.add("nx",      20)
sys2.add("ny",      5)
sys2.add("nz",      5)
sys2.use(fenics_heat_conduction)

k_vals = [15.0, 45.0, 100.0, 205.0, 385.0]   # steel, Ti, Al alloy, Al, Cu
labels = ["Steel", "Ti alloy", "Al alloy", "Aluminium", "Copper"]
sweep2 = sys2.sweep("k", k_vals)
print(f"  {'Material':>12}  {'k [W/mK]':>10}  {'Q [W]':>8}")
for i, (mat, k) in enumerate(zip(labels, k_vals)):
    row = sweep2.table.iloc[i]
    q   = row["heat_flux"]
    q_w = float(q.si) if hasattr(q, "si") else float(q)
    print(f"  {mat:>12}  {k:10.1f}  {q_w:8.3f}")
print("  (Q ∝ k: linear as expected from Fourier's law)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: fenics_linear_elasticity, fenics_heat_conduction → domain fem.fenics")
