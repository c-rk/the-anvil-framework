"""
Example 14: Materials — Fatigue, Fracture, and Composites
===========================================================

Demonstrates:
    - safety_factor RSQ             — margin of safety check
    - fatigue_life_basquin RSQ      — S-N curve (Basquin's law)
    - miners_rule RSQ               — cumulative fatigue damage (Miner's rule)
    - fracture_toughness_check RSQ  — linear elastic fracture mechanics
    - composite_laminate_stiffness RSQ — rule-of-mixtures composite stiffness
    - solve_forward()               — DAG systems
    - sweep()                       — fatigue life vs load amplitude

Engineering context:
    Structural life assessment of a rotating shaft in a turbopump.
    The shaft is made of high-strength steel, sees multiple load levels
    during a typical flight, and has a known surface crack from NDI.
"""

import sys, os
import numpy as np


import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 14: Materials — Fatigue, Fracture, Composites")
print("=" * 60)


# =====================================================
# Material: 300M High-Strength Steel (typical turbopump shaft)
# =====================================================
E_steel       = 207e9      # Pa — Young's modulus
sigma_y       = 1700e6     # Pa — 0.2% yield strength
sigma_uts     = 1950e6     # Pa — ultimate tensile strength
sigma_f_prime = 2100e6     # Pa — fatigue strength coefficient (Basquin)
b_exp         = -0.07      # —   Basquin exponent (typical for high-strength steel)
KIc           = 70e6       # Pa√m — plane strain fracture toughness

print(f"\n  Material: 300M Steel")
print(f"    E       = {E_steel/1e9:.0f} GPa")
print(f"    σ_y     = {sigma_y/1e6:.0f} MPa")
print(f"    σ_UTS   = {sigma_uts/1e6:.0f} MPa")
print(f"    σ_f'    = {sigma_f_prime/1e6:.0f} MPa  (Basquin coeff)")
print(f"    b       = {b_exp}  (Basquin exponent)")
print(f"    KIc     = {KIc/1e6:.0f} MPa√m")


# =====================================================
# 1. Safety Factor Check — nominal operating stress
# =====================================================
print("\n[1] Safety Factor — Nominal Operating Stress")

design_stress = 750e6    # Pa — stress amplitude at max load

r_sf = anvil.R.safety_factor(allowable_stress=sigma_y, applied_stress=design_stress)
def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
SF   = _v(r_sf["safety_factor"])
MoS  = _v(r_sf["margin_of_safety"])
pass_ = bool(r_sf["pass"])

print(f"\n  σ_applied = {design_stress/1e6:.0f} MPa,  σ_allowable = {sigma_y/1e6:.0f} MPa")
print(f"  Safety factor:   SF = {SF:.3f}  ({'PASS' if pass_ else 'FAIL'})")
print(f"  Margin of safety: MoS = {MoS:.3f}  ({MoS*100:.1f}%)")

# Sweep over applied stress to find failure boundary
sf_sys = System("safety_check")
sf_sys.add("allowable_stress", sigma_y, "Pa")
sf_sys.add("applied_stress",   design_stress, "Pa")
sf_sys.use("safety_factor")

sweep_sf = sf_sys.sweep("applied_stress", np.linspace(500e6, 2000e6, 7))
sweep_sf.summary(outputs=["safety_factor", "margin_of_safety", "pass"])


# =====================================================
# 2. Fatigue Life — Basquin's Law  N = (σ_a / σ_f')^(1/b)
# =====================================================
print("\n[2] Fatigue Life — Basquin's Law")

stress_amplitudes = [300e6, 500e6, 750e6, 1000e6, 1200e6]

print(f"\n  S-N curve for 300M Steel:")
print(f"  {'σ_a (MPa)':>12s}  {'N_cycles':>14s}  {'Life(flights)':>14s}")
print(f"  {'-'*42}")

flights_per_cycle = 100   # cycles per flight for this shaft

for sigma_a in stress_amplitudes:
    r_fat = anvil.R.fatigue_life_basquin(
        sigma_a=sigma_a,
        sigma_f_prime=sigma_f_prime,
        b_exponent=b_exp
    )
    N = _v(r_fat["N_cycles"])
    flights = N / flights_per_cycle
    print(f"  {sigma_a/1e6:>12.0f}  {N:>14.2e}  {flights:>14.1f}")

# Build a fatigue system for sweep
fatigue_sys = System("basquin_fatigue")
fatigue_sys.add("sigma_a",       design_stress, "Pa",  desc="Stress amplitude")
fatigue_sys.add("sigma_f_prime", sigma_f_prime, "Pa",  desc="Basquin coefficient")
fatigue_sys.add("b_exponent",    b_exp,                desc="Basquin exponent")
fatigue_sys.use("fatigue_life_basquin")

print(f"\n  Fatigue life sweep (stress amplitude vs N_cycles):")
sweep_fat = fatigue_sys.sweep("sigma_a", np.linspace(200e6, 1200e6, 8))
sweep_fat.summary(outputs=["N_cycles"])


# =====================================================
# 3. Miner's Rule — Cumulative Fatigue Damage
#
# Flight spectrum: 3 distinct load levels, each with
# a known number of cycles per flight.
# =====================================================
print("\n[3] Miner's Rule — Cumulative Damage")

# Flight spectrum: [stress level (Pa), cycles per flight]
spectrum = [
    ("Taxi/ground",     150e6,  500),   # low stress, many cycles
    ("Cruise",          400e6,   80),   # moderate stress
    ("Maneuver/launch", 750e6,   20),   # high stress, few cycles
]

# Compute fatigue life for each level
cycle_limits = []
cycle_counts = []
print(f"\n  Flight spectrum:")
print(f"  {'Level':20s}  {'σ_a(MPa)':>10s}  {'n/flight':>10s}  {'N_f':>14s}  {'n/N_f':>10s}")
print(f"  {'-'*68}")

for level, sigma_a, n_per_flight in spectrum:
    r_fat = anvil.R.fatigue_life_basquin(
        sigma_a=sigma_a, sigma_f_prime=sigma_f_prime, b_exponent=b_exp
    )
    N_f = _v(r_fat["N_cycles"])
    cycle_limits.append(N_f)
    cycle_counts.append(float(n_per_flight))
    ratio = n_per_flight / N_f
    print(f"  {level:20s}  {sigma_a/1e6:>10.0f}  {n_per_flight:>10d}  {N_f:>14.2e}  {ratio:>10.4e}")

# Compute damage per flight
damage_per_flight = sum(n / N for n, N in zip(cycle_counts, cycle_limits))
flights_to_failure = 1.0 / damage_per_flight

print(f"\n  Damage per flight: D = Σ(n/N) = {damage_per_flight:.6e}")
print(f"  Flights to failure (D = 1):  {flights_to_failure:.0f} flights")

# Full Miner's rule RSQ call
r_miner = anvil.R.miners_rule(
    cycle_counts=cycle_counts,
    cycle_limits=cycle_limits,
)
D_total = _v(r_miner["damage_index"])
failed  = bool(r_miner["failed"])
remain  = _v(r_miner["remaining_life_fraction"])

print(f"\n  After 1 flight:")
print(f"    Damage index D = {D_total:.6f}  ({'FAILED' if failed else 'OK'})")
print(f"    Remaining life fraction: {remain:.6f}")

# After 100 flights
cycle_counts_100 = [n * 100 for n in cycle_counts]
r_miner_100 = anvil.R.miners_rule(
    cycle_counts=cycle_counts_100,
    cycle_limits=cycle_limits,
)
D_100 = _v(r_miner_100["damage_index"])
print(f"\n  After 100 flights: D = {D_100:.4f}  ({'FAILED' if bool(r_miner_100['failed']) else 'OK'})")
print(f"  Flights to inspection limit (D=0.5): {0.5/damage_per_flight:.0f} flights")


# =====================================================
# 4. Fracture Toughness Check
#
# NDI detected a surface semi-circular crack of radius a.
# Check if the stress intensity factor KI exceeds KIc.
# =====================================================
print("\n[4] Fracture Toughness Check (LEFM)")

a_crack_ndi = 0.0008   # m — 0.8 mm crack from NDI (near detection limit)

print(f"\n  Crack size from NDI: a = {a_crack_ndi*1000:.1f} mm")
print(f"  KIc = {KIc/1e6:.0f} MPa√m")
print(f"\n  {'σ (MPa)':>10s}  {'KI (MPa√m)':>12s}  {'SF_frac':>10s}  {'Fail?':>8s}")
print(f"  {'-'*44}")

for sigma in [300e6, 500e6, 750e6, 1000e6, 1400e6]:
    r_frac = anvil.R.fracture_toughness_check(
        sigma=sigma,
        a_crack=a_crack_ndi,
        KIc=KIc,
        F_geometry=1.12,   # free-surface correction for semi-circular crack
    )
    KI    = _v(r_frac["KI"])
    sf_fr = _v(r_frac["safety_factor"])
    fail  = bool(r_frac["failed"])
    print(f"  {sigma/1e6:>10.0f}  {KI/1e6:>12.2f}  {sf_fr:>10.2f}  {'YES' if fail else 'no':>8s}")

# Critical crack size at operating stress
r_frac_op = anvil.R.fracture_toughness_check(
    sigma=design_stress, a_crack=a_crack_ndi, KIc=KIc
)
KI_op = _v(r_frac_op["KI"])
a_critical = (KIc / (1.12 * design_stress * np.sqrt(np.pi)))**2
print(f"\n  At operating stress {design_stress/1e6:.0f} MPa:")
print(f"    KI = {KI_op/1e6:.2f} MPa√m  (KIc = {KIc/1e6:.0f})")
print(f"    Critical crack size: a_crit = {a_critical*1000:.2f} mm")
print(f"    Safety factor: {_v(r_frac_op['safety_factor']):.2f}")


# =====================================================
# 5. Thermal Expansion Stress
# =====================================================
print("\n[5] Thermal Expansion Stress — cryogenic refueling")

# Temperature change during LOX propellant loading
E_al    = 72e9     # Pa — aluminum alloy
alpha_al = 23e-6   # 1/K — thermal expansion coefficient (aluminum)
dT_cry  = -180     # K — cryogenic cooling (ambient → -180°C delta)

r_th = anvil.R.thermal_expansion_stress(E=E_al, alpha_thermal=alpha_al, dT=dT_cry)
sigma_th = abs(_v(r_th["sigma_thermal"]))

print(f"\n  Aluminum structure (E={E_al/1e9:.0f} GPa, α={alpha_al*1e6:.0f} µ/K)")
print(f"  Cooling ΔT = {dT_cry} K (cryogenic LOX loading)")
print(f"  Thermal stress: σ_th = {sigma_th/1e6:.0f} MPa")

sigma_y_al = 503e6  # Pa — Al 7075-T6
r_sf_th = anvil.R.safety_factor(allowable_stress=sigma_y_al, applied_stress=sigma_th)
print(f"  Safety factor (Al 7075-T6, σ_y={sigma_y_al/1e6:.0f} MPa): {_v(r_sf_th['safety_factor']):.2f}")


# =====================================================
# 6. Composite Laminate Stiffness (rule of mixtures)
# =====================================================
print("\n[6] Composite Laminate Stiffness (CFRP)")

# Carbon fiber / epoxy composite (typical UD ply)
Ef     = 230e9   # Pa — fiber modulus (carbon)
Em     = 3.5e9   # Pa — matrix modulus (epoxy)
Gf     = 90e9    # Pa — fiber shear modulus
Gm     = 1.3e9   # Pa — matrix shear modulus
nu_f   = 0.20    # — fiber Poisson's ratio
nu_m   = 0.35    # — matrix Poisson's ratio
Vf     = 0.60    # — fiber volume fraction (60%)

r_comp = anvil.R.composite_laminate_stiffness(
    Ef=Ef, Em=Em, Gf=Gf, Gm=Gm, nu_f=nu_f, nu_m=nu_m, Vf=Vf
)

E1  = _v(r_comp["E1"])
E2  = _v(r_comp["E2"])
G12 = _v(r_comp["G12"])
nu12 = _v(r_comp["nu12"])

print(f"\n  CFRP UD ply (Vf = {Vf*100:.0f}%):")
print(f"    E1   = {E1/1e9:.1f} GPa  (axial — fiber dominated)")
print(f"    E2   = {E2/1e9:.2f} GPa  (transverse — matrix dominated)")
print(f"    G12  = {G12/1e9:.2f} GPa  (shear)")
print(f"    ν12  = {nu12:.4f}")
print(f"    E1/E2 ratio = {E1/E2:.1f}  (strong anisotropy)")

# Sweep Vf
comp_sys = System("composite_design")
comp_sys.add("Ef",   Ef);   comp_sys.add("Em",   Em)
comp_sys.add("Gf",   Gf);   comp_sys.add("Gm",   Gm)
comp_sys.add("nu_f", nu_f); comp_sys.add("nu_m", nu_m)
comp_sys.add("Vf",   Vf)
comp_sys.use("composite_laminate_stiffness")

print(f"\n  Stiffness vs fiber volume fraction:")
sweep_comp = comp_sys.sweep("Vf", np.linspace(0.35, 0.70, 7))
sweep_comp.summary(outputs=["E1", "E2", "G12", "nu12"])


# =====================================================
# 7. Full structural assessment system
# =====================================================
print("\n[7] Integrated structural life system")

struct_sys = System("shaft_life_assessment")
struct_sys.add("sigma_a",       design_stress,  "Pa")
struct_sys.add("sigma_f_prime", sigma_f_prime,  "Pa")
struct_sys.add("b_exponent",    b_exp)
struct_sys.add("allowable_stress", sigma_y,     "Pa")
struct_sys.add("applied_stress",   design_stress, "Pa")
struct_sys.add("sigma",            design_stress, "Pa")
struct_sys.add("a_crack",          a_crack_ndi)
struct_sys.add("KIc",              KIc)
struct_sys.add("F_geometry",       1.12)
struct_sys.use("fatigue_life_basquin")
struct_sys.use("safety_factor")
struct_sys.use("fracture_toughness_check")

r_final = struct_sys.solve_forward()
print(f"\n  Integrated assessment at σ={design_stress/1e6:.0f} MPa:")
print(f"    Fatigue life:     {_v(r_final['N_cycles']):.2e} cycles")
print(f"    Static SF:        {_v(r_final['safety_factor']):.2f}")
print(f"    Fracture KI/KIc:  {_v(r_final['KI'])/_v(r_final['KIc']):.3f}"
      f"  ({'CRITICAL' if bool(r_final['failed']) else 'safe'})")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
