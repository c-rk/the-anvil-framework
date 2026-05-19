"""
Example 17: Rayleigh Flow via Project Registry
===============================================

Demonstrates:
    - Defining custom RSQs and registering them in a project registry
    - rayleigh_ratios: flow property ratios at a given M (T0/T0*, P/P*, etc.)
    - rayleigh_heat:   exit conditions from inlet state + heat addition [J/kg]
    - System + solve_forward()
    - sweep() over heat addition range
    - proj.promote() to push a finished RSQ to the global registry

Engineering context:
    Constant-area duct with heat addition (Rayleigh flow) — models a
    combustion chamber, afterburner, or any duct where heat is added
    without friction. Given inlet Mach, stagnation temperature, and
    static pressure, find exit conditions for a range of heat loads.
"""

import sys, os
import numpy as np


import anvil
from anvil import Q, solvers

print("=" * 60)
print("  Example 17: Rayleigh Flow via Project Registry")
print("=" * 60)


# =====================================================
# 1. Define the RSQs as plain Python functions
# =====================================================

def rayleigh_ratios(M, gamma=1.4):
    """Rayleigh flow ratios at Mach M referenced to sonic (★) conditions."""
    g = float(gamma); M = float(M)
    gp1 = g + 1
    denom = 1 + g * M**2
    P_Pstar     = gp1 / denom
    T_Tstar     = (gp1 * M / denom)**2
    rho_rhostar = denom / (gp1 * M**2)
    t0          = 1 + (g - 1) / 2 * M**2
    T0_T0star   = 2 * gp1 * M**2 * t0 / denom**2
    P0_P0star   = P_Pstar * (2 * t0 / gp1) ** (g / (g - 1))
    return {
        "T0_T0star":   T0_T0star,
        "T_Tstar":     T_Tstar,
        "P_Pstar":     P_Pstar,
        "P0_P0star":   P0_P0star,
        "rho_rhostar": rho_rhostar,
        "V_Vstar":     1.0 / rho_rhostar,
    }


def rayleigh_heat(M1, T01, P1, q_heat, cp, gamma=1.4):
    """
    Rayleigh flow with heat addition in a constant-area duct.
    q_heat [J/kg]: >0 heating, <0 cooling.
    Raises ValueError if heat addition would choke the flow.
    """
    g      = float(gamma); M1 = float(M1)
    T01    = float(getattr(T01,    "si", T01))
    P1     = float(getattr(P1,     "si", P1))
    q_heat = float(getattr(q_heat, "si", q_heat))
    cp     = float(getattr(cp,     "si", cp))
    gp1 = g + 1

    def _T0r(M):
        d = 1 + g * M**2
        return 2 * gp1 * M**2 * (1 + (g - 1) / 2 * M**2) / d**2
    def _Pr(M):  return gp1 / (1 + g * M**2)
    def _Tr(M):  return (gp1 * M / (1 + g * M**2))**2

    r1     = _T0r(M1)
    T02    = T01 + q_heat / cp
    T0star = T01 / r1
    r2     = T02 / T0star

    if r2 > 1.0:
        raise ValueError(
            f"Flow chokes: T02/T0* = {r2:.4f} > 1.0. "
            f"Max q_heat = {cp * (T0star - T01):.1f} J/kg"
        )

    bracket = (1.0001, 50.0) if M1 >= 1.0 else (0.001, 0.9999)
    M2  = solvers.find_root(lambda M: _T0r(M) - r2, bracket=bracket,
                            method="brent", tol=1e-12)
    P2  = P1  / _Pr(M1) * _Pr(M2)
    T1  = T01 / (1 + (g - 1) / 2 * M1**2)
    T2  = T1  / _Tr(M1) * _Tr(M2)
    P01 = P1  * (1 + (g - 1) / 2 * M1**2) ** (g / (g - 1))
    P02 = P2  * (1 + (g - 1) / 2 * M2**2) ** (g / (g - 1))
    return {
        "M2":        M2,
        "T02":       Q(T02, "K"),
        "T2":        Q(T2,  "K"),
        "P2":        Q(P2,  "Pa"),
        "P02":       Q(P02, "Pa"),
        "P01":       Q(P01, "Pa"),
        "P02_P01":   P02 / P01,
        "T0_T0star": r2,
    }


# =====================================================
# 2. Push to a project registry
# =====================================================

proj = anvil.project("rayleigh_study", path="./rayleigh_work")

proj.push(rayleigh_ratios,
          domain="aero.compressible",
          description="Rayleigh flow ratios at Mach M referenced to sonic conditions",
          tags=["rayleigh", "compressible", "heat_addition"])

proj.push(rayleigh_heat,
          domain="aero.compressible",
          description="Rayleigh flow exit conditions given inlet state + heat addition",
          tags=["rayleigh", "compressible", "heat_addition", "combustion"])

print("\n--- Project registry contents ---")
proj.list()


# =====================================================
# 3. Verify ratios at M=1 (all should equal 1.0)
# =====================================================

print("\n--- rayleigh_ratios at M=1.0 (all ratios = 1.0) ---")
r = proj.R.rayleigh_ratios(M=1.0)
for k, v in r.items():
    print(f"  {k:15s} = {v:.6f}")


# =====================================================
# 4. Build a System and solve
#    Inlet: M=0.3, T01=400 K, P1=200 kPa, q=300 kJ/kg (air)
# =====================================================

print("\n--- System solve: single heat addition ---")

duct = anvil.system("rayleigh_duct")
duct.add("M1",     0.3)
duct.add("T01",    400.0,   "K")
duct.add("P1",     200e3,   "Pa")
duct.add("q_heat", 300e3,   "J/kg")
duct.add("cp",     1005.0,  "J/kg/K")
duct.add("gamma",  1.4)
duct.use(proj.R.rayleigh_heat)

result = duct.solve_forward()
result.summary()


# =====================================================
# 5. Sweep heat addition from 0 to 80% of choke limit
# =====================================================

print("\n--- Sweep: q_heat from 0 to 80% of choke limit ---")

# Find choke limit for these inlet conditions
r_inlet = proj.R.rayleigh_ratios(M=0.3, gamma=1.4)
T0star  = 400.0 / r_inlet["T0_T0star"]
q_choke = 1005.0 * (T0star - 400.0)
print(f"  Choke limit: q_max = {q_choke/1e3:.1f} kJ/kg")

q_values = np.linspace(0, 0.80 * q_choke, 30)
sweep = duct.sweep("q_heat", q_values, skip_errors=True)
sweep.summary(outputs=["M2", "T02", "P2", "P02_P01"])


# =====================================================
# 6. Promote to global registry when satisfied
# =====================================================

# Uncomment when ready to make these globally available:
# proj.promote("rayleigh_ratios")
# proj.promote("rayleigh_heat")
# print("\nPromoted rayleigh_ratios and rayleigh_heat to global registry.")
# print("Now accessible as anvil.R.rayleigh_ratios / anvil.R.rayleigh_heat")
