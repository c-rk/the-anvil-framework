"""
Example 1: Rocket Nozzle Design Trade Study
============================================

Demonstrates:
    - Loading a pre-built System from the registry
    - Overriding inputs with .set()
    - Parametric sweeps
    - Unit conversions on results
    - anvil.check() for inspection

Engineering context:
    Design a rocket nozzle by varying chamber pressure and area ratio
    to find optimal thrust and specific impulse.
"""

import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil import Q

print("=" * 60)
print("  Example 1: Rocket Nozzle Design")
print("=" * 60)

# --- Step 1: Inspect what's available ---
print("\n[1] Inspecting the rocket_nozzle system...")
anvil.check("rocket_nozzle")

# --- Step 2: Load and customize ---
print("\n[2] Loading nozzle with custom propellant properties...")
nozzle = anvil.S.rocket_nozzle.copy()

# LOX/LH2 propellant properties
nozzle.set(
    P0=20e6,          # 20 MPa chamber pressure (high-performance engine)
    T0=3500,           # 3500 K combustion temperature
    gamma=1.20,        # typical for LOX/LH2
    R_gas=520,         # J/kg/K for LOX/LH2 products
    A_throat=0.005,    # 50 cm^2 throat
    A_exit=0.08,       # 800 cm^2 exit
    P_amb=0,           # vacuum (space engine)
)

result = nozzle.solve()
result.summary()

# --- Step 3: Unit conversions ---
print("\n[3] Key results in different units:")
print(f"  Thrust:  {result['thrust'].to('kN').value:.1f} kN")
print(f"           {result['thrust'].to('lbf').value:.0f} lbf")
print(f"  Isp:     {result['Isp'].value:.1f} s")
print(f"  Exit V:  {result['V_exit'].to('km/s').value:.2f} km/s")
print(f"  mdot:    {result['mdot'].value:.2f} kg/s")

# --- Step 4: Trade study -- chamber pressure ---
print("\n[4] Sweep: Thrust and Isp vs chamber pressure...")
sweep = nozzle.sweep("P0", np.linspace(5e6, 30e6, 6))
sweep.summary(outputs=["thrust", "Isp", "mdot", "M_exit"])

# --- Step 5: Trade study -- area ratio ---
print("\n[5] Sweep: Performance vs exit area...")
nozzle.set(P0=20e6)  # reset
sweep2 = nozzle.sweep("A_exit", np.linspace(0.02, 0.15, 6))
sweep2.summary(outputs=["thrust", "Isp", "M_exit", "P_exit"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
