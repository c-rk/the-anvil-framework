"""
Example 10: Chapman-Jouguet Detonation Analysis
=================================================

Demonstrates:
    - NASA CEA adapter with proper SI unit handling
    - All quantities defined with explicit units
    - Unit conversions via .to() throughout
    - System composition: detonation system feeding into PDE nozzle
    - Parametric sweeps with correct unit display

Falls back to published reference data if NASA CEA is not installed.
"""

import os
import sys

import numpy as np


import anvil
from anvil.adapters.nasa_cea_detonation import cea_detonation
from anvil import Q, System

print("=" * 60)
print("  Example 10: Chapman-Jouguet Detonation")
print("=" * 60)

# =====================================================
# 1. Direct detonation calls (inputs in SI)
# =====================================================
print("\n[1] CJ detonation for common mixtures (at 1 atm, 300 K):\n")

P_init = Q(1, "atm")  # define pressure with units
T_init = Q(300, "K")

print(
    f"  Initial: P = {P_init.value} {P_init.unit} ({P_init.to('Pa').value:.0f} Pa), T = {T_init.value} {T_init.unit}"
)
print()
print(f"  {'Mixture':25s} {'D_CJ':>10s} {'T_CJ':>10s} {'P2/P1':>8s} {'P_CJ':>10s}")
print(f"  {'-' * 65}")

cases = [
    ("H2/O2", "H2", "O2", 2.0, 1.0, None),
    ("H2/Air", "H2", "O2", 2.0, 1.0, {"N2": 3.76}),
    ("CH4/O2", "CH4", "O2", 1.0, 2.0, None),
    ("C2H4/O2", "C2H4", "O2", 1.0, 3.0, None),
]

for label, fuel, ox, fm, om, extra in cases:
    r = cea_detonation(
        fuel=fuel,
        oxidizer=ox,
        fuel_moles=fm,
        ox_moles=om,
        T1=T_init.si,
        P1=P_init.si,
        extra_species=extra,
    )
    print(
        f"  {label:25s} {r['D_CJ'].value:10.0f} m/s {r['T_CJ'].value:10.0f} K "
        f"{r['P_ratio']:8.1f} {r['P_CJ'].to('atm').value:10.2f} atm"
    )


# =====================================================
# 2. Anvil System with proper units
# =====================================================
print(f"\n[2] H2/O2 detonation system (all quantities with units):")

det = System("h2o2_detonation")
det.add("fuel_moles", 2.0, desc="Moles of H2")
det.add("ox_moles", 1.0, desc="Moles of O2")
det.add("T1", 300, "K", desc="Initial temperature")
det.add("P1", 1, "atm", desc="Initial pressure")


def h2o2_det(fuel_moles, ox_moles, T1, P1):
    """Wrapper: Anvil passes SI values (K, Pa) which the adapter handles."""
    return cea_detonation(
        fuel="H2", oxidizer="O2", fuel_moles=fuel_moles, ox_moles=ox_moles, T1=T1, P1=P1
    )


det.use(h2o2_det)

result = det.solve_forward()
result.summary(
    keys=[
        "fuel_moles",
        "ox_moles",
        "T1",
        "P1",
        "D_CJ",
        "T_CJ",
        "P_CJ",
        "P_ratio",
        "gamma_CJ",
        "MW_CJ",
        "a_CJ",
    ]
)

# Unit conversions using the engine
print(f"\n  Key results (unit engine conversions):")
print(
    f"    D_CJ  = {result['D_CJ'].value:.0f} {result['D_CJ'].unit}  ({result['D_CJ'].to('km/s').value:.3f} km/s)"
)
print(f"    T_CJ  = {result['T_CJ'].value:.0f} {result['T_CJ'].unit}")
print(
    f"    P_CJ  = {result['P_CJ'].to('atm').value:.2f} atm  ({result['P_CJ'].to('bar').value:.2f} bar)"
)


# =====================================================
# 3. Sweep: initial pressure
# =====================================================
print(f"\n[3] Sweep: D_CJ vs initial pressure...")
sweep_p = det.sweep("P1", np.array([0.5, 1.0, 2.0, 5.0, 10.0, 20.0]))
sweep_p.summary(outputs=["D_CJ", "T_CJ", "P_ratio", "P_CJ"])


# =====================================================
# 4. Sweep: initial temperature
# =====================================================
print(f"\n[4] Sweep: D_CJ vs initial temperature...")
det.set(P1=1)  # reset to 1 atm
sweep_t = det.sweep("T1", np.linspace(250, 600, 5))
sweep_t.summary(outputs=["D_CJ", "T_CJ", "P_ratio", "a_CJ"])


# =====================================================
# 5. Sensitivity analysis
# =====================================================
print(f"\n[5] Sensitivity: what drives D_CJ?")
det.set(T1=300, P1=1)
sens = det.sensitivity(outputs=["D_CJ", "T_CJ"])
sens.summary()


# =====================================================
# 6. COMPOSITION: Detonation system -> PDE nozzle
# =====================================================
print(f"\n[6] Composition: Detonation -> PDE Nozzle")
print(f"    The det system is used as a sub-system feeding the nozzle.\n")

# Build the PDE system that USES the det system via composition
pde = System("pulse_det_engine")

# PDE inputs (same names as det system, so composition inherits them)
pde.add("fuel_moles", 2.0)
pde.add("ox_moles", 1.0)
pde.add("T1", 300, "K", desc="Initial mixture temperature")
pde.add("P1", 600, "psi", desc="Initial mixture pressure")
pde.add("A_throat", 0.005, "m^2", desc="Nozzle throat area")
pde.add("A_exit", 0.05, "m^2", desc="Nozzle exit area")
pde.add("P_amb", 101325, "Pa", desc="Ambient pressure")

# USE the detonation system as a sub-system (composition!)
pde.use(det)

# Nozzle expansion of detonation products
pde.use("nozzle_area_ratio")
pde.use("area_mach_supersonic", map={"gamma": "gamma_CJ"})


def pde_exit(T_CJ, P_CJ, gamma_CJ, MW_CJ, M_exit):
    """Compute nozzle exit conditions from CJ state."""
    R_gas = 8314.46 / (MW_CJ * 1000)  # MW_CJ is in kg/mol
    T0_T = 1 + ((gamma_CJ - 1) / 2) * M_exit**2
    P0_P = T0_T ** (gamma_CJ / (gamma_CJ - 1))
    T_exit = T_CJ / T0_T
    P_exit = P_CJ / P0_P
    V_exit = M_exit * (gamma_CJ * R_gas * T_exit) ** 0.5
    return {
        "T_exit": Q(T_exit, "K"),
        "P_exit": Q(P_exit, "Pa"),
        "V_exit": Q(V_exit, "m/s"),
    }


def pde_performance(
    P_CJ, A_throat, gamma_CJ, MW_CJ, T_CJ, V_exit, P_exit, P_amb, A_exit
):
    """Compute PDE thrust and Isp."""
    R_gas = 8314.46 / (MW_CJ * 1000)
    t = (2 / (gamma_CJ + 1)) ** ((gamma_CJ + 1) / (2 * (gamma_CJ - 1)))
    mdot = P_CJ * A_throat * (gamma_CJ / (R_gas * T_CJ)) ** 0.5 * t
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    Isp = F / (mdot * 9.80665)
    return {
        "mdot_pde": Q(mdot, "kg/s"),
        "thrust_pde": Q(F, "N"),
        "Isp_pde": Q(Isp, "s"),
    }


pde.use(pde_exit)
pde.use(pde_performance)

r_pde = pde.solve_forward()
r_pde.summary(
    keys=[
        "T1",
        "P1",
        "fuel_moles",
        "ox_moles",
        "D_CJ",
        "T_CJ",
        "P_CJ",
        "M_exit",
        "V_exit",
        "thrust_pde",
        "Isp_pde",
        "mdot_pde",
    ]
)

print(f"\n  PDE performance (unit conversions):")
print(
    f"    Thrust = {r_pde['thrust_pde'].to('kN').value:.2f} kN ({r_pde['thrust_pde'].to('lbf').value:.0f} lbf)"
)
print(f"    Isp    = {r_pde['Isp_pde'].value:.1f} {r_pde['Isp_pde'].unit}")
print(f"    V_exit = {r_pde['V_exit'].to('km/s').value:.3f} km/s")

# Sweep the PDE over initial pressure
print(f"\n  Sweep: PDE performance vs initial pressure...")
sweep_pde = pde.sweep("P1", np.array([0.5, 1.0, 2.0, 5.0, 10.0]))
sweep_pde.summary(outputs=["D_CJ", "T_CJ", "thrust_pde", "Isp_pde"])


# =====================================================
# 7. Export
# =====================================================
print(f"\n[7] Exporting results...")
r_pde.to_csv("pde_results.csv")
print(f"  Saved: pde_results.csv")
sweep_pde.to_csv("pde_pressure_sweep.csv", outputs=["D_CJ", "thrust_pde", "Isp_pde"])
print(f"  Saved: pde_pressure_sweep.csv")

# Cleanup
os.remove("pde_results.csv")
os.remove("pde_pressure_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
