"""
Example 12: Project Registry
==============================

Demonstrates:
    - anvil.project() — create an isolated per-project RSQ store
    - proj.push()     — register draft RSQs to the project store
    - proj.R.*        — access project RSQs via namespace
    - Context manager — routes anvil.push() to the project
    - proj.search()   — fuzzy search within the project
    - proj.list()     — list all project RSQs
    - proj.promote()  — move a tested RSQ to the global registry
    - Multiple projects open simultaneously

Engineering context:
    You're developing new heat-exchanger correlations. Use a project
    store to iterate on drafts without polluting the global registry.
    Promote only the final, validated correlations.
"""

import sys, os, tempfile
import numpy as np


import anvil
from anvil import Q, System

# Use a temp directory so the example is self-contained
_tmp = tempfile.mkdtemp(prefix="anvil_ex12_")

print("=" * 60)
print("  Example 12: Project Registry")
print("=" * 60)


# =====================================================
# 1. Open a project store
# =====================================================
print("\n[1] Opening project store for 'hx_correlations'...")

proj = anvil.project("hx_correlations", path=_tmp)
print(f"  Repr: {proj}")


# =====================================================
# 2. Push draft RSQs to the project
# =====================================================
print("\n[2] Registering draft correlations...")

def ntu_crossflow(UA, C_min, C_max):
    """NTU for cross-flow heat exchanger (both fluids unmixed)."""
    NTU = UA / C_min
    C_r = C_min / C_max
    # Kays & London correlation
    eps = 1 - np.exp((NTU**0.22 / C_r) * (np.exp(-C_r * NTU**0.78) - 1))
    return {"NTU_cf": NTU, "effectiveness_cf": eps, "C_ratio": C_r}

def shell_tube_ntu(UA, mdot_shell, mdot_tube, Cp_shell, Cp_tube):
    """NTU and effectiveness for 1-shell-pass 2-tube-pass (TEMA E)."""
    C_shell = mdot_shell * Cp_shell
    C_tube  = mdot_tube  * Cp_tube
    C_min   = min(C_shell, C_tube)
    C_max   = max(C_shell, C_tube)
    NTU     = UA / C_min
    C_r     = C_min / C_max
    # Shah & Sekulic formula for 1-2 shell-and-tube
    if C_r < 1.0:
        sqrt_term = np.sqrt(1 + C_r**2)
        eps = 2 / (1 + C_r + sqrt_term * (1 + np.exp(-NTU * sqrt_term)) / (1 - np.exp(-NTU * sqrt_term)))
    else:
        eps = NTU / (1 + NTU)   # limit for C_r → 1
    return {
        "NTU_st": NTU,
        "effectiveness_st": eps,
        "C_min_st": Q(C_min, "W/K"),
        "C_max_st": Q(C_max, "W/K"),
    }

def log_mean_temp(T_hot_in, T_hot_out, T_cold_in, T_cold_out):
    """Log Mean Temperature Difference for counter-flow arrangement."""
    dT1 = T_hot_in  - T_cold_out
    dT2 = T_hot_out - T_cold_in
    if abs(dT1 - dT2) < 1e-6:
        LMTD = dT1
    else:
        LMTD = (dT1 - dT2) / np.log(dT1 / max(dT2, 1e-6))
    return {"LMTD": Q(LMTD, "K")}

proj.push(ntu_crossflow,   domain="heat_transfer", description="Cross-flow NTU (Kays & London)")
proj.push(shell_tube_ntu,  domain="heat_transfer", description="1-2 shell-and-tube NTU (Shah & Sekulic)")
proj.push(log_mean_temp,   domain="heat_transfer", description="Log Mean Temperature Difference")

proj.list()


# =====================================================
# 3. Use project RSQs directly
# =====================================================
print("\n[3] Direct calls via proj.R.*")

r_cf = proj.R.ntu_crossflow(UA=3500, C_min=1800, C_max=2400)
print(f"\n  Cross-flow HX (UA=3500, C_min=1800):")
print(f"    NTU         = {r_cf['NTU_cf']:.3f}")
print(f"    C_ratio     = {r_cf['C_ratio']:.3f}")
print(f"    effectiveness = {r_cf['effectiveness_cf']:.4f}")

r_st = proj.R.shell_tube_ntu(UA=5000, mdot_shell=2.0, mdot_tube=1.5,
                               Cp_shell=4186, Cp_tube=1005)
print(f"\n  Shell-and-tube HX (UA=5000):")
print(f"    NTU         = {r_st['NTU_st']:.3f}")
print(f"    effectiveness = {r_st['effectiveness_st']:.4f}")


# =====================================================
# 4. Build a System using project RSQs
# =====================================================
print("\n[4] System using project RSQ for outlet temperature calculation...")

def outlet_temps_from_eff(effectiveness_cf, C_min, C_hot_in, T_hot_in, T_cold_in, C_hot, C_cold):
    Q_actual = effectiveness_cf * C_min * (T_hot_in - T_cold_in)
    T_hot_out  = T_hot_in  - Q_actual / C_hot
    T_cold_out = T_cold_in + Q_actual / C_cold
    return {
        "Q_actual": Q(Q_actual, "W"),
        "T_hot_out":  Q(T_hot_out,  "K"),
        "T_cold_out": Q(T_cold_out, "K"),
    }

hx = System("crossflow_hx")
hx.add("T_hot_in",   450,   "K")
hx.add("T_cold_in",  290,   "K")
hx.add("mdot_hot",   1.2,   "kg/s")
hx.add("mdot_cold",  2.0,   "kg/s")
hx.add("Cp_hot",    1050,   "J/kg/K")
hx.add("Cp_cold",   4186,   "J/kg/K")
hx.add("UA",        3500,   "W/K")

def compute_capacity_rates(mdot_hot, Cp_hot, mdot_cold, Cp_cold):
    C_hot  = mdot_hot  * Cp_hot
    C_cold = mdot_cold * Cp_cold
    C_min  = min(C_hot, C_cold)
    C_max  = max(C_hot, C_cold)
    C_hot_in = C_hot   # pass through for outlet_temps
    return {"C_hot": Q(C_hot, "W/K"), "C_cold": Q(C_cold, "W/K"),
            "C_min": Q(C_min, "W/K"), "C_max": Q(C_max, "W/K"),
            "C_hot_in": Q(C_hot, "W/K")}

hx.use(compute_capacity_rates)
hx.use(proj.R.ntu_crossflow)     # project RSQ used directly in System
hx.use(outlet_temps_from_eff)

result = hx.solve_forward()
result.summary(keys=["T_hot_in", "T_cold_in", "UA",
                      "NTU_cf", "effectiveness_cf",
                      "T_hot_out", "T_cold_out", "Q_actual"])


# =====================================================
# 5. Context manager — route anvil.push() to project
# =====================================================
print("\n[5] Context manager: push drafts inside 'with' block...")

proj2 = anvil.project("fouling_study", path=_tmp)

with proj2:
    @anvil.relation(domain="heat_transfer", register=False)
    def fouling_resistance(mdot, rho_fluid, mu_fluid, D_tube, L_tube, k_fluid):
        """Estimate fouling resistance from Dittus-Boelter Nu and fouling factor."""
        V = mdot / (rho_fluid * np.pi * (D_tube / 2)**2)
        Re = rho_fluid * V * D_tube / mu_fluid
        Pr = mu_fluid * 4186 / k_fluid   # approximate Prandtl
        Nu = 0.023 * Re**0.8 * Pr**0.4  # Dittus-Boelter
        h = Nu * k_fluid / D_tube
        Rf = 0.0002    # typical fouling resistance (m^2·K/W)
        U_fouled = 1.0 / (1.0 / h + Rf)
        A_tube = np.pi * D_tube * L_tube
        return {"Re_tube": Re, "Nu_tube": Nu, "h_tube": Q(h, "W/m^2/K"),
                "U_fouled": Q(U_fouled, "W/m^2/K"), "UA_fouled": Q(U_fouled * A_tube, "W/K")}

    proj2.push(fouling_resistance)

# Outside the with block — context no longer active
proj2.list()

r_foul = proj2.R.fouling_resistance(
    mdot=0.5, rho_fluid=1000, mu_fluid=0.001,
    D_tube=0.02, L_tube=2.0, k_fluid=0.6
)
print(f"\n  Fouling study (D={20}mm, L=2m):")
print(f"    Re      = {r_foul['Re_tube']:.0f}")
print(f"    Nu      = {r_foul['Nu_tube']:.0f}")
print(f"    h       = {r_foul['h_tube']}")
print(f"    UA_foul = {r_foul['UA_fouled']}")


# =====================================================
# 6. Search within project
# =====================================================
print("\n[6] Searching project for 'NTU'...")
proj.search("NTU")

print("\n  Searching for 'effectiveness'...")
proj.search("effectiveness")


# =====================================================
# 7. Promote a tested RSQ to global registry
# =====================================================
print("\n[7] Promoting 'log_mean_temp' to global registry...")

# Verify it isn't already global
existing = anvil.registry.search("log_mean_temp")
if not existing:
    proj.promote("log_mean_temp")
    print("  Verifying it's in global registry:")
    anvil.registry.search("log_mean_temp")

    # Use via global namespace
    r_lmtd = anvil.R.log_mean_temp(
        T_hot_in=result["T_hot_in"].si,
        T_hot_out=result["T_hot_out"].si,
        T_cold_in=result["T_cold_in"].si,
        T_cold_out=result["T_cold_out"].si,
    )
    print(f"\n  LMTD via global registry: {r_lmtd['LMTD']}")

    # Clean up global registry
    anvil.registry.remove("log_mean_temp")
    print("  Cleaned up: removed 'log_mean_temp' from global registry.")
else:
    print("  (already in global registry)")


# =====================================================
# 8. Two projects open simultaneously
# =====================================================
print("\n[8] Two projects open simultaneously (no conflict)...")

proj_a = anvil.project("project_A", path=_tmp)
proj_b = anvil.project("project_B", path=_tmp)

def my_rsq_v1(x, k=1.0):
    return {"y_v1": k * x}

def my_rsq_v2(x, k=1.2):
    return {"y_v2": k * x + 0.5}

proj_a.push(my_rsq_v1, domain="test")
proj_b.push(my_rsq_v2, domain="test")

ra = proj_a.R.my_rsq_v1(x=5.0)
rb = proj_b.R.my_rsq_v2(x=5.0)
print(f"\n  Project A — my_rsq_v1(5): y = {ra['y_v1']}")
print(f"  Project B — my_rsq_v2(5): y = {rb['y_v2']}")
print(f"  Global registry: unaffected (no 'my_rsq_v1' or 'my_rsq_v2' there)")


# =====================================================
# Cleanup temp directory
# =====================================================
import shutil
shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
