"""
Example 5: Supersonic Wind Tunnel Sizing
=========================================

Demonstrates:
    - Composing a System from multiple registry RSQs
    - Normal shock + isentropic flow analysis
    - Name mapping for generic Relations
    - Proper unit propagation through all outputs
    - Full design workflow: define -> solve -> sweep -> analyze

Engineering context:
    Size a blowdown supersonic wind tunnel for Mach 2.5 testing.
    Compute required settling chamber conditions, test section
    properties, and diffuser recovery after a normal shock.
"""

import os
import sys

import numpy as np


import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 5: Supersonic Wind Tunnel Design")
print("=" * 60)

# --- Requirements (use Quantities from the start) ---
M_test = 2.5
T_test = Q(300, "K")
P_test = Q(50, "kPa")
gamma = 1.4

print(f"\n[1] Test section requirements:")
print(f"  Mach   = {M_test}")
print(f"  T_test = {T_test.value} {T_test.unit}")
print(f"  P_test = {P_test.value} {P_test.unit} ({P_test.to('atm').value:.3f} atm)")

# --- Step 2: Compute stagnation conditions ---
print(f"\n[2] Stagnation conditions (from isentropic ratios):")
ratios = anvil.R.isentropic_ratios(M=M_test, gamma=gamma)

T0 = Q(T_test.si * ratios["T0_T"], "K")
P0 = Q(P_test.si * ratios["P0_P"], "Pa")

print(f"  T0/T = {ratios['T0_T']:.4f}  -->  T0 = {T0.value:.1f} {T0.unit}")
print(
    f"  P0/P = {ratios['P0_P']:.4f}  -->  P0 = {P0.to('kPa').value:.1f} kPa ({P0.to('atm').value:.2f} atm)"
)

# --- Step 3: Normal shock at test section Mach ---
print(f"\n[3] Normal shock at M = {M_test}:")
shock = anvil.R.normal_shock(M1=M_test, gamma=gamma)
print(f"  M2 (downstream) = {shock['M2']:.4f}")
print(f"  P2/P1 = {shock['P2_P1']:.3f}")
print(f"  T2/T1 = {shock['T2_T1']:.3f}")
print(f"  Stagnation pressure recovery = {shock['P02_P01']:.4f}")

P0_recovered = Q(P0.si * shock["P02_P01"], "Pa")
print(f"  --> Diffuser exit P0 = {P0_recovered.to('kPa').value:.1f} kPa")

# --- Step 4: Prandtl-Meyer expansion ---
print(f"\n[4] Maximum turning angle (Prandtl-Meyer):")
pm = anvil.R.prandtl_meyer(M=M_test, gamma=gamma)
print(f"  nu(M={M_test}) = {pm['nu_deg']:.2f} degrees")

# --- Step 5: Build full tunnel system ---
print(f"\n[5] Full tunnel analysis system:")

tunnel = System("wind_tunnel")
tunnel.add("M_test", M_test)
tunnel.add("T_test", T_test.si, "K", desc="Test section static temperature")
tunnel.add("P_test", P_test.si, "Pa", desc="Test section static pressure")
tunnel.add("gamma", gamma)
tunnel.add("R_gas", 287.058, "J/kg/K", desc="Air gas constant")
tunnel.add("A_test", 0.04, "m^2", desc="Test section area (20x20 cm)")

# Isentropic ratios at test Mach
tunnel.use("isentropic_ratios", map={"M": "M_test"})

# Speed of sound and velocity in test section
tunnel.use("speed_of_sound", map={"T": "T_test"})


def test_velocity(M_test, a):
    return {"V_test": Q(M_test * a, "m/s")}


tunnel.use(test_velocity)


def rho_from_ideal(P_test, R_gas, T_test):
    return {"rho_test": Q(P_test / (R_gas * T_test), "kg/m^3")}


tunnel.use(rho_from_ideal)

# Dynamic pressure in test section
tunnel.use("dynamic_pressure", map={"rho": "rho_test", "V": "V_test"})


# Stagnation conditions
def stagnation_conditions(T_test, P_test, T0_T, P0_P):
    return {"T0": Q(T_test * T0_T, "K"), "P0": Q(P_test * P0_P, "Pa")}


tunnel.use(stagnation_conditions)

# Normal shock at test Mach
tunnel.use("normal_shock", map={"M1": "M_test"})

result = tunnel.solve_forward()
result.summary(
    keys=[
        "M_test",
        "T_test",
        "P_test",
        "A_test",
        "T0",
        "P0",
        "V_test",
        "rho_test",
        "q_inf",
        "M2",
        "P2_P1",
        "P02_P01",
    ]
)

# --- Unit conversions using the unit engine ---
print(f"\n  Key results (converted via unit engine):")
print(
    f"  T0 = {result['T0'].value:.1f} {result['T0'].unit}  ({result['T0'].to('R').value:.1f} R)"
)
print(
    f"  P0 = {result['P0'].to('kPa').value:.1f} kPa  ({result['P0'].to('atm').value:.2f} atm)"
)
print(f"  V_test = {result['V_test'].value:.1f} {result['V_test'].unit}")
print(f"  q_inf  = {result['q_inf'].to('kPa').value:.2f} kPa")

# --- Step 6: Sweep test Mach ---
print(f"\n[6] Sweep: tunnel conditions vs test Mach...")
sweep = tunnel.sweep("M_test", np.array([1.5, 2.0, 2.5, 3.0, 3.5, 4.0]))
sweep.summary(outputs=["T0", "P0", "V_test", "q_inf", "P02_P01"])

# --- Step 7: Reynolds number at test section ---
print(f"\n[7] Reynolds number at test conditions:")
mu_result = anvil.R.sutherland_viscosity(T=T_test.si)
Re_result = anvil.R.reynolds_number(
    rho=result["rho_test"].si,
    V=result["V_test"].si,
    L_char=0.2,
    mu=mu_result["mu"].si,
)
print(f"  mu_air(300 K) = {mu_result['mu'].value:.3e} {mu_result['mu'].unit}")
print(f"  Re (20 cm model) = {Re_result['Re']:.3e}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
