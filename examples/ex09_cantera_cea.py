"""
Example 9: Cantera Combustion + Nozzle Design
===============================================

A complete rocket engine analysis using Cantera for combustion
thermochemistry and Anvil's built-in nozzle system for performance.

PREREQUISITES:
    conda install -c cantera cantera
    -- OR --
    pip install cantera

If Cantera is not installed, this example uses a built-in mock
so you can see the full workflow. Replace USE_MOCK = False when
Cantera is available.

WHAT THIS EXAMPLE DOES:
    1. Compute combustion products at equilibrium (like NASA CEA)
    2. Feed Tc, gamma, R_gas into the nozzle system
    3. Sweep O/F ratio to find optimal Isp
    4. Sweep chamber pressure for thrust trades
    5. Compare H2/O2 vs CH4/O2 propellant combinations
    6. Sensitivity analysis on the full engine
    7. Export results for reports
"""

import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil import Q, System, Adapter

# =====================================================
# Check if Cantera is available
# =====================================================
USE_MOCK = True
try:
    import cantera as ct
    USE_MOCK = False
    print(f"  Cantera {ct.__version__} found. Using real thermochemistry.")
except ImportError:
    print("  Cantera not installed. Using built-in mock data.")
    print("  To install: conda install -c cantera cantera")
    print()

print("=" * 60)
print("  Example 9: Cantera Combustion + Nozzle Design")
print("=" * 60)


# =====================================================
# Combustion adapter (real or mock)
# =====================================================

if not USE_MOCK:
    # Real Cantera adapter
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from adapters.cantera_thermo import cea_rocket
else:
    # Mock adapter using curve fits (same interface as real)
    def _mock_cea(fuel="H2", oxidizer="O2", OF=6.0, Pc=10e6, **kw):
        """Mock CEA using published data for H2/O2 and CH4/O2."""
        fuel_lower = fuel.lower()
        if fuel_lower in ("h2", "hydrogen"):
            # H2/O2: Tc peaks near O/F=4, Isp peaks near O/F=4-5
            OF_opt, Tc_peak = 4.0, 3250
            gamma_base, R_base, MW_base = 1.14, 530, 15.7
        elif fuel_lower in ("ch4", "methane"):
            # CH4/O2: Tc peaks near O/F=3.5
            OF_opt, Tc_peak = 3.5, 3530
            gamma_base, R_base, MW_base = 1.13, 355, 23.4
        else:
            OF_opt, Tc_peak = 3.0, 3400
            gamma_base, R_base, MW_base = 1.15, 380, 21.9

        Tc = Tc_peak * (1 - 0.12 * ((OF - OF_opt) / OF_opt)**2)
        Tc *= (1 + 0.015 * np.log(max(Pc, 1e5) / 1e6))
        gamma = gamma_base + 0.02 * (OF / OF_opt - 1)
        MW = MW_base + 1.5 * (OF - OF_opt)
        R_gas = 8314.46 / MW
        cstar = np.sqrt(gamma * R_gas * Tc) / (
            gamma * np.sqrt((2 / (gamma + 1))**((gamma + 1) / (gamma - 1))))

        return {
            "Tc": Q(Tc, "K"), "gamma_c": gamma,
            "R_gas_c": Q(R_gas, "J/kg/K"), "MW_c": Q(MW / 1000, "kg/mol"),
            "rho_c": Q(Pc / (R_gas * Tc), "kg/m^3"),
            "cstar": Q(cstar, "m/s"),
        }

    cea_rocket = Adapter("cea_rocket_mock",
        backend="python", call=_mock_cea,
        inputs={"fuel": {"default": "H2"}, "oxidizer": {"default": "O2"},
                "OF": {"default": 6.0}, "Pc": {"unit": "Pa", "default": 10e6}},
        outputs={"Tc": {"unit": "K"}, "gamma_c": {}, "R_gas_c": {"unit": "J/kg/K"},
                 "MW_c": {"unit": "kg/mol"}, "rho_c": {"unit": "kg/m^3"},
                 "cstar": {"unit": "m/s"}},
        desc="Mock CEA combustion (replace with real Cantera)",
        tags=["combustion", "mock"])


# =====================================================
# 1. Direct combustion call
# =====================================================
print("\n[1] H2/O2 combustion at O/F=5, Pc=20 MPa:")
r = cea_rocket(fuel="H2", oxidizer="O2", OF=5.0, Pc=20e6)
print(f"  Tc     = {r['Tc'].value:.0f} K")
print(f"  gamma  = {r['gamma_c']:.4f}")
print(f"  R_gas  = {r['R_gas_c'].value:.1f} J/kg/K")
print(f"  c*     = {r['cstar'].value:.0f} m/s")


# =====================================================
# 2. Build full engine system
# =====================================================
print("\n[2] Full H2/O2 engine system:")

engine = System("h2o2_engine")
engine.add("OF",        5.0,          desc="Oxidizer/fuel ratio")
engine.add("Pc",        20e6,  "Pa",  desc="Chamber pressure")
engine.add("A_throat",  0.01,  "m^2", desc="Throat area")
engine.add("A_exit",    0.15,  "m^2", desc="Exit area")
engine.add("P_amb",     0,     "Pa",  desc="Vacuum")

# Combustion -- fix propellant choice, vary OF and Pc
def h2o2_combustion(OF, Pc):
    return cea_rocket(fuel="H2", oxidizer="O2", OF=OF, Pc=Pc)
engine.use(h2o2_combustion)

# Nozzle (from registry)
engine.use("nozzle_area_ratio")
engine.use("area_mach_supersonic", map={"gamma": "gamma_c"})

# Isentropic + exit conditions using combustion products
def exit_analysis(Tc, Pc, gamma_c, R_gas_c, M_exit):
    T0_T = 1 + ((gamma_c - 1) / 2) * M_exit**2
    P0_P = T0_T ** (gamma_c / (gamma_c - 1))
    T_exit = Tc / T0_T
    P_exit = Pc / P0_P
    a_exit = (gamma_c * R_gas_c * T_exit)**0.5
    V_exit = M_exit * a_exit
    return {"T_exit": Q(T_exit, "K"), "P_exit": Q(P_exit, "Pa"),
            "V_exit": Q(V_exit, "m/s")}

def thrust_isp(Pc, A_throat, gamma_c, R_gas_c, Tc, V_exit, P_exit, P_amb, A_exit):
    t = (2 / (gamma_c + 1))**((gamma_c + 1) / (2 * (gamma_c - 1)))
    mdot = Pc * A_throat * (gamma_c / (R_gas_c * Tc))**0.5 * t
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    Isp = F / (mdot * 9.80665)
    return {"mdot": Q(mdot, "kg/s"), "thrust": Q(F, "N"), "Isp": Q(Isp, "s")}

engine.use(exit_analysis)
engine.use(thrust_isp)

result = engine.solve_forward()
result.summary(keys=["OF", "Pc",
                       "Tc", "gamma_c", "R_gas_c", "cstar",
                       "M_exit", "V_exit", "thrust", "Isp"])

print(f"\n  Performance:")
print(f"    Thrust (vac): {result['thrust'].to('kN').value:.1f} kN")
print(f"    Isp (vac):    {result['Isp'].value:.1f} s")
print(f"    c*:           {result['cstar'].value:.0f} m/s")


# =====================================================
# 3. O/F ratio sweep
# =====================================================
print("\n[3] Sweep: Isp vs O/F ratio (H2/O2)...")
sweep_of = engine.sweep("OF", np.linspace(3.0, 8.0, 6))
sweep_of.summary(outputs=["Tc", "gamma_c", "cstar", "Isp", "thrust"])


# =====================================================
# 4. Chamber pressure sweep
# =====================================================
print("\n[4] Sweep: Performance vs chamber pressure...")
engine.set(OF=5.0)  # reset to near-optimal
sweep_pc = engine.sweep("Pc", np.linspace(5e6, 30e6, 6))
sweep_pc.summary(outputs=["Tc", "cstar", "thrust", "Isp", "mdot"])


# =====================================================
# 5. Propellant comparison: H2/O2 vs CH4/O2
# =====================================================
print("\n[5] Propellant comparison:")
print(f"  {'Propellant':20s} {'Tc(K)':>8s} {'gamma':>8s} {'Isp(s)':>8s} {'c*(m/s)':>8s}")
print(f"  {'-'*56}")

for fuel_name, ox_name, of_ratio in [
    ("H2",  "O2", 5.0),
    ("CH4", "O2", 3.5),
]:
    # Rebuild engine with different propellant
    eng2 = System(f"{fuel_name}_{ox_name}_engine")
    eng2.add("OF", of_ratio); eng2.add("Pc", 20e6, "Pa")
    eng2.add("A_throat", 0.01, "m^2"); eng2.add("A_exit", 0.15, "m^2")
    eng2.add("P_amb", 0, "Pa")
    def make_comb(f, o):
        def comb(OF, Pc): return cea_rocket(fuel=f, oxidizer=o, OF=OF, Pc=Pc)
        return comb
    eng2.use(make_comb(fuel_name, ox_name))
    eng2.use("nozzle_area_ratio")
    eng2.use("area_mach_supersonic", map={"gamma": "gamma_c"})
    eng2.use(exit_analysis); eng2.use(thrust_isp)
    r = eng2.solve_forward()
    print(f"  {fuel_name + '/' + ox_name:20s} "
          f"{r['Tc'].value:8.0f} {r['gamma_c'].si:8.4f} "
          f"{r['Isp'].value:8.1f} {r['cstar'].value:8.0f}")


# =====================================================
# 6. Sensitivity analysis
# =====================================================
print("\n[6] Sensitivity: what drives Isp?")
engine.set(OF=5.0, Pc=20e6)
sens = engine.sensitivity(outputs=["Isp", "thrust"])
sens.summary(outputs=["Isp"])

print(f"\n  Top drivers of Isp:")
for inp, val in sens.top("Isp", n=5):
    print(f"    {inp}: {val:+.4f}")


# =====================================================
# 7. Export for report
# =====================================================
print("\n[7] Exporting data...")
result = engine.solve_forward()
result.to_csv("engine_h2o2.csv")
print("  Saved: engine_h2o2.csv")

sweep_of.to_csv("of_sweep_h2o2.csv", outputs=["Tc", "Isp", "thrust", "cstar"])
print("  Saved: of_sweep_h2o2.csv")

json_str = result.to_json("engine_h2o2.json")
print("  Saved: engine_h2o2.json")

# Show CSV content
print("\n  CSV preview:")
with open("engine_h2o2.csv") as f:
    for line in f.readlines()[:8]:
        print(f"    {line.rstrip()}")

# Cleanup
os.remove("engine_h2o2.csv")
os.remove("of_sweep_h2o2.csv")
os.remove("engine_h2o2.json")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
