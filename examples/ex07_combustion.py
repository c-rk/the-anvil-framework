"""
Example 7: Combustion Chamber Analysis (Cantera-Style Adapter)
==============================================================

Demonstrates:
    - Writing an Adapter for a thermochemistry library
    - Mock Cantera interface (works without Cantera installed)
    - Composition: combustion -> nozzle -> performance
    - Sensitivity analysis: which inputs drive Isp?

Engineering context:
    Model a rocket combustion chamber using equilibrium thermochemistry.
    The combustion adapter computes gas properties (Tc, gamma, R_gas, MW)
    which feed into the nozzle system for thrust and Isp.

    If you have Cantera installed, replace the mock with real calls.
    See docs/ADAPTER_GUIDE.md for the full Cantera adapter template.
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System, Adapter

print("=" * 60)
print("  Example 7: Combustion + Nozzle Analysis")
print("=" * 60)

# =====================================================
# Mock Cantera adapter (replace with real Cantera calls)
# =====================================================

def mock_equilibrium(Pc, OF, fuel_name="RP1", oxidizer_name="LOX"):
    """
    Mock combustion equilibrium. In production, this would call:
        import cantera as ct
        gas = ct.Solution('gri30.yaml')
        gas.set_equivalence_ratio(1/OF, fuel, oxidizer)
        gas.TP = 300, Pc
        gas.equilibrate('HP')
        return {"Tc": gas.T, "gamma": gas.cp/gas.cv, ...}

    This mock uses curve fits for LOX/RP-1 performance.
    """
    # Simplified curve fits (real Cantera would compute these exactly)
    # Based on NASA CEA data for LOX/RP-1
    OF_opt = 2.7  # optimal O/F ratio
    Tc_peak = 3670  # K at optimal O/F

    # Temperature varies with O/F (parabolic approximation)
    Tc = Tc_peak * (1 - 0.15 * ((OF - OF_opt) / OF_opt)**2)
    # Slight pressure dependence
    Tc = Tc * (1 + 0.02 * np.log(Pc / 1e6))

    # Molecular weight and gamma vary with O/F
    MW = 22.0 + 2.0 * (OF - 2.0)  # g/mol, approximate
    R_gas = 8314.46 / MW  # J/kg/K
    gamma = 1.15 + 0.03 * (OF - 2.0)  # approximate

    # Characteristic velocity
    cstar = (R_gas * Tc / gamma * ((gamma + 1) / 2)**((gamma + 1) / (gamma - 1)))**0.5

    return {
        "Tc": Q(Tc, "K"),
        "gamma_c": gamma,
        "R_gas_c": Q(R_gas, "J/kg/K"),
        "MW": Q(MW, "g/mol"),
        "cstar": Q(cstar, "m/s"),
    }


combustion = Adapter("lox_rp1_equilibrium",
    backend="python",
    call=mock_equilibrium,
    inputs={
        "Pc":   {"unit": "Pa", "desc": "Chamber pressure"},
        "OF":   {"desc": "Oxidizer-to-fuel mass ratio", "default": 2.7},
        "fuel_name": {"desc": "Fuel identifier", "default": "RP1"},
        "oxidizer_name": {"desc": "Oxidizer identifier", "default": "LOX"},
    },
    outputs={
        "Tc":     {"unit": "K",      "desc": "Chamber temperature"},
        "gamma_c": {"desc": "Ratio of specific heats"},
        "R_gas_c": {"unit": "J/kg/K", "desc": "Specific gas constant"},
        "MW":     {"unit": "g/mol",  "desc": "Mean molecular weight"},
        "cstar":  {"unit": "m/s",    "desc": "Characteristic velocity"},
    },
    desc="LOX/RP-1 equilibrium combustion (mock Cantera)",
    tags=["combustion", "propulsion", "cantera"],
)

# --- Direct call ---
print("\n[1] Direct combustion call (O/F = 2.7, Pc = 10 MPa):")
r = combustion(Pc=10e6, OF=2.7)
for k, v in r.items():
    if isinstance(v, Q):
        print(f"  {k:12s} = {v.value:.2f} {v.unit}")
    else:
        print(f"  {k:12s} = {v:.4f}")

# =====================================================
# Build integrated combustion + nozzle system
# =====================================================
print("\n[2] Integrated combustion + nozzle system:")

engine = System("lox_rp1_engine")

# Design inputs
engine.add("Pc",       10e6,    "Pa",  desc="Chamber pressure")
engine.add("OF",       2.7,            desc="O/F ratio")
engine.add("A_throat", 0.02,    "m^2", desc="Throat area")
engine.add("A_exit",   0.30,    "m^2", desc="Exit area")
engine.add("P_amb",    101325,  "Pa",  desc="Ambient pressure (sea level)")

# Combustion (adapter)
engine.use(combustion)

# Nozzle physics (from registry, with name mapping)
engine.use("nozzle_area_ratio")
engine.use("area_mach_supersonic")
engine.use("isentropic_ratios", map={"M": "M_exit", "gamma": "gamma_c"})

def exit_conditions_mapped(Tc, Pc, T0_T, P0_P, gamma_c, R_gas_c):
    T_exit = Tc / T0_T
    P_exit = Pc / P0_P
    a_exit = (gamma_c * R_gas_c * T_exit)**0.5
    return {"T_exit": Q(T_exit, "K"), "P_exit": Q(P_exit, "Pa"),
            "a_exit": Q(a_exit, "m/s")}
engine.use(exit_conditions_mapped)

def exit_velocity(M_exit, a_exit):
    return {"V_exit": Q(M_exit * a_exit, "m/s")}
engine.use(exit_velocity)

def choked_flow(Pc, A_throat, gamma_c, R_gas_c, Tc):
    t = (2 / (gamma_c + 1))**((gamma_c + 1) / (2 * (gamma_c - 1)))
    mdot = Pc * A_throat * (gamma_c / (R_gas_c * Tc))**0.5 * t
    return {"mdot": Q(mdot, "kg/s")}
engine.use(choked_flow)

engine.use("rocket_thrust", map={"P_exit": "P_exit", "V_exit": "V_exit"})
engine.use("specific_impulse")

result = engine.solve_forward()
result.summary(keys=["Pc", "OF", "A_throat", "A_exit",
                       "Tc", "gamma_c", "R_gas_c", "cstar",
                       "M_exit", "V_exit", "mdot", "thrust", "Isp"])

# --- Unit conversions ---
print(f"\n[3] Engine performance:")
print(f"  Thrust (SL):  {result['thrust'].to('kN').value:.1f} kN")
print(f"  Isp (SL):     {result['Isp'].value:.1f} s")
print(f"  c*:           {result['cstar'].value:.0f} m/s")
print(f"  Mass flow:    {result['mdot'].value:.1f} kg/s")

# --- O/F ratio trade study ---
print(f"\n[4] Sweep: Isp vs O/F ratio...")
sweep = engine.sweep("OF", np.linspace(1.5, 4.0, 8))
sweep.summary(outputs=["Tc", "gamma_c", "cstar", "Isp", "thrust"])

# --- Sensitivity analysis ---
print(f"\n[5] Sensitivity analysis (which inputs drive Isp?):")
sens = engine.sensitivity(outputs=["Isp", "thrust"])
sens.summary()

print("\n  Top 3 drivers of Isp:")
for inp, val in sens.top("Isp", n=3):
    print(f"    {inp}: {val:+.4f}")

# --- Export ---
print(f"\n[6] Exporting results...")
result.to_csv("engine_results.csv")
print(f"  Saved: engine_results.csv")
sweep.to_csv("of_sweep.csv", outputs=["Tc", "Isp", "thrust"])
print(f"  Saved: of_sweep.csv")
json_str = result.to_json()
print(f"  JSON preview: {json_str[:100]}...")

# Cleanup
os.remove("engine_results.csv")
os.remove("of_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
