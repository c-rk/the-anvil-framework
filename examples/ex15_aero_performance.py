"""
Example 15: Aerodynamic Performance Analysis
=============================================

Demonstrates:
    - isa_atmosphere RSQ      — ISA standard atmosphere at any altitude
    - thin_airfoil_cl RSQ     — thin airfoil lift slope + Prandtl-Glauert
    - induced_drag RSQ        — induced drag from lift coefficient
    - drag_polar RSQ          — full drag polar (CDi + CD0)
    - oswald_efficiency RSQ   — Oswald efficiency for swept wings
    - stall_speed RSQ         — minimum speed (stall)
    - range_breguet RSQ       — Breguet range equation (jet aircraft)
    - solve_forward()         — DAG system for aircraft sizing
    - sweep()                 — performance vs altitude trade study
    - in_ alias               — `in` as unit (inches)

Engineering context:
    Conceptual design of a subsonic jet transport. Compute lift,
    drag, stall speed, and cruise range at different altitudes
    using the full ISA atmosphere.
"""

import sys, os
import numpy as np


import anvil
from anvil import Q, System
from anvil import in_    # `in` is a Python keyword; Anvil provides `in_`

print("=" * 60)
print("  Example 15: Aerodynamic Performance Analysis")
print("=" * 60)


# =====================================================
# Aircraft parameters (narrow-body jet transport)
# =====================================================
W_MTOW     = 750e3    # N  — max takeoff weight (≈76 t)
W_OEW      = 420e3    # N  — operating empty weight
S_ref      = 122.4    # m^2 — wing reference area
AR         = 9.5      # — aspect ratio
sweep_deg  = 25.0     # deg — quarter-chord sweep
taper      = 0.25     # — taper ratio
CD0        = 0.025    # — zero-lift drag coefficient
CLmax      = 2.8      # — max lift coefficient (flaps extended)
TSFC       = 1.8e-5   # kg/N/s — thrust specific fuel consumption (SI)

print(f"\n  Aircraft parameters:")
print(f"    MTOW   = {W_MTOW/1e3:.0f} kN ({W_MTOW/9.80665/1000:.0f} t)")
print(f"    S_ref  = {S_ref} m²,  AR = {AR},  Sweep = {sweep_deg}°")
print(f"    CD0    = {CD0},  CLmax = {CLmax}")
print(f"    TSFC   = {TSFC:.2e} kg/N/s")

# Demonstrate in_ alias (inches as a unit)
wing_chord = 5.5 * in_    # 5.5 inches (model scale test)
print(f"\n  Model scale test chord: {5.5} in = {wing_chord.to('m').value:.4f} m")
print(f"  (in_ alias used since 'in' is a Python keyword)")


# =====================================================
# 1. ISA Standard Atmosphere
# =====================================================
print("\n[1] ISA Standard Atmosphere")

altitudes = [0, 5000, 10000, 11000, 15000, 20000]

print(f"\n  {'h (m)':>8s}  {'T (K)':>8s}  {'P (kPa)':>10s}  {'ρ (kg/m³)':>12s}  {'a (m/s)':>10s}")
print(f"  {'-'*54}")

for h in altitudes:
    r_isa = anvil.R.isa_atmosphere(h=h)
    def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
    T   = _v(r_isa["T_atm"])
    P   = _v(r_isa["P_atm"])
    rho = _v(r_isa["rho_atm"])
    a   = _v(r_isa["a_atm"])
    print(f"  {h:>8.0f}  {T:>8.2f}  {P/1000:>10.3f}  {rho:>12.4f}  {a:>10.2f}")


# =====================================================
# 2. Thin Airfoil Theory + Prandtl-Glauert Correction
# =====================================================
print("\n[2] Thin Airfoil Lift Coefficient (with Prandtl-Glauert)")

angles = [-4, 0, 2, 4, 6, 8, 10]
machs  = [0.0, 0.3, 0.6, 0.75]

print(f"\n  CL vs angle-of-attack (α_L0 = -2°):")
print(f"  {'α (°)':>8s}", end="")
for M in machs:
    print(f"  {'M='+str(M):>10s}", end="")
print()
print(f"  {'-'*48}")

for alpha in angles:
    print(f"  {alpha:>8.1f}", end="")
    for M in machs:
        r_cl = anvil.R.thin_airfoil_cl(alpha_deg=float(alpha), alpha_L0_deg=-2.0, M=M)
        CL = _v(r_cl["CL"])
        print(f"  {CL:>10.4f}", end="")
    print()

print(f"\n  CL_alpha (2π/rad × P-G) at M=0.6:")
r_cla = anvil.R.thin_airfoil_cl(alpha_deg=5.0, alpha_L0_deg=-2.0, M=0.6)
print(f"    CL_alpha = {_v(r_cla['CL_alpha']):.4f} per degree  ({_v(r_cla['CL_alpha'])*180/np.pi:.4f}/rad)")


# =====================================================
# 3. Oswald Efficiency + Drag Polar
# =====================================================
print("\n[3] Drag Polar and L/D at Cruise")

r_oswald = anvil.R.oswald_efficiency(AR=AR, sweep_deg=sweep_deg, taper=taper)
e_oswald = _v(r_oswald["e_oswald"])
print(f"\n  Oswald efficiency: e = {e_oswald:.4f}  (AR={AR}, sweep={sweep_deg}°)")

CL_cruise  = 0.52   # typical cruise CL

r_polar = anvil.R.drag_polar(CL=CL_cruise, CD0=CD0, AR=AR, e=e_oswald)
CD_cr   = _v(r_polar["CD"])
CDi_cr  = _v(r_polar["CDi"])
LoD_cr  = _v(r_polar["LoD"])

print(f"\n  At CL = {CL_cruise} (cruise):")
print(f"    CD0  = {CD0:.4f}  (parasite drag)")
print(f"    CDi  = {CDi_cr:.4f}  (induced drag)")
print(f"    CD   = {CD_cr:.4f}  (total)")
print(f"    L/D  = {LoD_cr:.2f}  (lift-to-drag)")

# Sweep CL to find L/D max
polar_sys = System("wing_polar")
polar_sys.add("CL",  0.5)
polar_sys.add("CD0", CD0)
polar_sys.add("AR",  AR)
polar_sys.add("e",   e_oswald)
polar_sys.use("drag_polar")

print(f"\n  L/D vs CL (drag polar sweep):")
sweep_polar = polar_sys.sweep("CL", np.linspace(0.2, 1.2, 9))
sweep_polar.summary(outputs=["CDi", "CD", "LoD"])

# Find optimum CL
LoD_vals = [_v(sweep_polar["LoD"][i]) if hasattr(sweep_polar["LoD"][i], "si")
            else float(sweep_polar["LoD"][i])
            for i in range(len(sweep_polar["LoD"]))]
CL_vals  = np.linspace(0.2, 1.2, 9)
idx_opt  = np.argmax(LoD_vals)
print(f"\n  Optimal CL = {CL_vals[idx_opt]:.2f}  (L/D_max = {LoD_vals[idx_opt]:.2f})")
print(f"  Analytical: CL_opt = sqrt(π·e·AR·CD0) = {np.sqrt(np.pi*e_oswald*AR*CD0):.3f}")


# =====================================================
# 4. Stall Speed at Different Altitudes
# =====================================================
print("\n[4] Stall Speed vs Altitude")

print(f"\n  {'Alt (m)':>8s}  {'ρ (kg/m³)':>12s}  {'V_stall (m/s)':>14s}  {'V_stall (kt)':>14s}")
print(f"  {'-'*52}")

for h in [0, 2000, 5000, 8000, 10000]:
    r_isa = anvil.R.isa_atmosphere(h=h)
    rho   = _v(r_isa["rho_atm"])
    r_stall = anvil.R.stall_speed(W=W_MTOW, rho=rho, S_ref=S_ref, CLmax=CLmax)
    Vs = _v(r_stall["V_stall"])
    Vs_kt = Vs / 0.5144    # m/s → knots
    print(f"  {h:>8.0f}  {rho:>12.4f}  {Vs:>14.1f}  {Vs_kt:>14.1f}")


# =====================================================
# 5. Induced Drag at Different Lift Coefficients
# =====================================================
print("\n[5] Induced Drag RSQ")

CDi_sys = System("induced_drag")
CDi_sys.add("CL", 0.52)
CDi_sys.add("AR", AR)
CDi_sys.add("e",  e_oswald)
CDi_sys.use("induced_drag")

r_cdi = CDi_sys.solve_forward()
print(f"\n  CL={0.52}, AR={AR}, e={e_oswald:.4f}:")
print(f"    CDi = {_v(r_cdi['CDi']):.5f}")

sweep_cdi = CDi_sys.sweep("CL", np.linspace(0.1, 1.2, 8))
sweep_cdi.summary(outputs=["CDi"])


# =====================================================
# 6. Breguet Range — cruise altitude trade study
# =====================================================
print("\n[6] Breguet Range vs Cruise Altitude")

# Fuel weight = MTOW - OEW (fully loaded)
W_fuel = W_MTOW - W_OEW

print(f"\n  Fuel weight: {W_fuel/1e3:.0f} kN  ({W_fuel/9.80665/1000:.0f} t)")
print(f"  TSFC = {TSFC:.2e} kg/N/s = {TSFC*9.80665*3600:.4f} /hr")

print(f"\n  Breguet range at different cruise altitudes:")
print(f"  {'Alt (m)':>8s}  {'TAS (m/s)':>10s}  {'Mach':>6s}  {'ρ':>10s}  {'L/D':>6s}  {'Range (km)':>12s}")
print(f"  {'-'*60}")

for h_cruise in [7000, 9000, 10668, 12000]:    # FL230, FL295, FL350 (36kft), FL394
    r_isa  = anvil.R.isa_atmosphere(h=h_cruise)
    rho    = _v(r_isa["rho_atm"])
    a_spd  = _v(r_isa["a_atm"])

    # Compute cruise Mach from CL = W/(0.5*rho*V^2*S)
    V_cruise = np.sqrt(W_MTOW / (0.5 * rho * S_ref * CL_cruise))
    M_cruise = V_cruise / a_spd

    # L/D at this condition
    r_pol = anvil.R.drag_polar(CL=CL_cruise, CD0=CD0, AR=AR, e=e_oswald)
    LoD   = _v(r_pol["LoD"])

    # Breguet range
    r_bq = anvil.R.range_breguet(
        V=V_cruise,
        TSFC=TSFC,
        LoD=LoD,
        W_initial=W_MTOW,
        W_final=W_OEW,
    )
    range_km = _v(r_bq["range_km"])

    print(f"  {h_cruise:>8.0f}  {V_cruise:>10.1f}  {M_cruise:>6.3f}  {rho:>10.4f}  {LoD:>6.2f}  {range_km:>12.0f}")


# =====================================================
# 7. Integrated aircraft performance System
# =====================================================
print("\n[7] Integrated aircraft performance System")

acft = System("aircraft_performance")
acft.add("h_cruise",   10668,   "m",      desc="Cruise altitude (FL350)")
acft.add("W_initial",  W_MTOW,  "N",      desc="Initial weight (MTOW)")
acft.add("W_final",    W_OEW,   "N",      desc="Final weight (OEW)")
acft.add("S_ref",      S_ref,   "m^2",    desc="Wing reference area")
acft.add("AR",         AR,                desc="Aspect ratio")
acft.add("CD0",        CD0,               desc="Zero-lift drag coefficient")
acft.add("CLmax",      CLmax,             desc="Max lift coefficient (flaps)")
acft.add("TSFC",       TSFC,             desc="Thrust specific fuel consumption")
acft.add("sweep_deg",  sweep_deg,         desc="Wing quarter-chord sweep")
acft.add("taper",      taper,             desc="Wing taper ratio")
acft.add("CL_cruise",  CL_cruise,         desc="Cruise lift coefficient")
acft.add("e_base",     0.85,              desc="Base Oswald efficiency (fallback)")

def isa_and_cruise(h_cruise):
    r = anvil.R.isa_atmosphere(h=h_cruise)
    def v(x): return float(x.si) if hasattr(x, "si") else float(x)
    return {"rho_cr": Q(v(r["rho_atm"]), "kg/m^3"),
            "a_cr":   Q(v(r["a_atm"]),   "m/s"),
            "T_cr":   Q(v(r["T_atm"]),   "K"),
            "P_cr":   Q(v(r["P_atm"]),   "Pa")}

def cruise_speed_and_mach(W_initial, S_ref, CL_cruise, rho_cr, a_cr):
    V = float((W_initial / (0.5 * float(rho_cr.si if hasattr(rho_cr, 'si') else rho_cr)
                             * float(S_ref.si if hasattr(S_ref, 'si') else S_ref)
                             * (CL_cruise.si if hasattr(CL_cruise, 'si') else CL_cruise)))**0.5)
    a  = float(a_cr.si if hasattr(a_cr, 'si') else a_cr)
    return {"V_cr": Q(V, "m/s"), "M_cr": V / a}

def polar_and_range(CL_cruise, CD0, AR, e_base, V_cr, TSFC, W_initial, W_final):
    CL = float(CL_cruise.si if hasattr(CL_cruise, 'si') else CL_cruise)
    e  = float(e_base.si if hasattr(e_base, 'si') else e_base)
    r  = anvil.R.drag_polar(CL=CL, CD0=float(CD0.si if hasattr(CD0, 'si') else CD0),
                              AR=float(AR.si if hasattr(AR, 'si') else AR), e=e)
    def v(x): return float(x.si) if hasattr(x, "si") else float(x)
    LoD = v(r["LoD"])
    V   = v(V_cr)
    tsfc = v(TSFC)
    Wi   = v(W_initial)
    Wf   = v(W_final)
    rng_r = anvil.R.range_breguet(V=V, TSFC=tsfc, LoD=LoD, W_initial=Wi, W_final=Wf)
    return {"LoD_cr": LoD, "CD_cr": v(r["CD"]), "CDi_cr": v(r["CDi"]),
            "range_km": Q(v(rng_r["range_km"]), "km")}

acft.use(isa_and_cruise)
acft.use(cruise_speed_and_mach)
acft.use(polar_and_range)

r_acft = acft.solve_forward()
def v(x): return float(x.si) if hasattr(x, "si") else float(x)
print(f"\n  Cruise performance summary (FL350 / {10668} m):")
print(f"    V_cruise = {v(r_acft['V_cr']):.1f} m/s  (M = {v(r_acft['M_cr']):.3f})")
print(f"    L/D      = {v(r_acft['LoD_cr']):.2f}")
print(f"    Range    = {v(r_acft['range_km']):.0f} km")

# Sweep altitude
print(f"\n  Range vs cruise altitude:")
sweep_alt = acft.sweep("h_cruise", np.array([7000, 8000, 9000, 10000, 11000, 12000, 13000]))
sweep_alt.summary(outputs=["T_cr", "rho_cr", "M_cr", "LoD_cr", "range_km"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
