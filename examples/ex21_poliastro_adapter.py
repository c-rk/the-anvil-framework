"""
Example 21: poliastro Adapter -- Orbit Design in Anvil
=======================================================

Demonstrates the poliastro adapter for orbit state, Hohmann transfers,
and propagation, all wired into Anvil Systems.

poliastro is used automatically when installed; the adapters fall back
to exact analytical two-body solutions otherwise.

PREREQUISITES:
    pip install poliastro astropy     (optional -- example runs without it)

WHAT THIS EXAMPLE DOES:
    1. Direct adapter calls -- LEO, GTO, polar orbit state
    2. Hohmann transfers -- LEO->GEO, GEO->Moon vicinity
    3. Orbit as an Anvil System -- chain with delta-v RSQ
    4. Sweep: transfer dv vs target altitude
    5. Sensitivity: which orbital parameter drives velocity most?
    6. Propagate orbit -- quarter/half/full period checks
    7. Orbit raise mission: LEO->GEO total budget with propellant mass
"""

import sys
import os
import math
import numpy as np


import anvil
from anvil import Q

from anvil.adapters.poliastro_orbits import (
    poliastro_orbit, poliastro_hohmann, poliastro_propagate, register
)

W = 64
R_E   = 6371e3      # m
MU_E  = 3.986004418e14

print("=" * W)
print("  Example 21: poliastro Adapter")
print("=" * W)

try:
    import poliastro
    print(f"  poliastro {poliastro.__version__} found.")
except ImportError:
    print("  poliastro not installed -- running in analytical mock mode.")

print()


# ── 1. Direct adapter calls ───────────────────────────────────────────────────
print("[1] Orbit state -- direct adapter calls")

orbits = [
    ("ISS / LEO",  R_E + 407e3,  0.0000, math.radians(51.6)),
    ("GTO",        24396e3,      0.7311, math.radians(27.0)),
    ("GEO",        42164e3,      0.0000, math.radians(0.0)),
    ("Polar LEO",  R_E + 500e3,  0.0000, math.radians(98.0)),
]

print(f"  {'Label':14s}  {'a (km)':>10s}  {'ecc':>6s}  {'T (min)':>8s}  {'v (m/s)':>9s}")
print(f"  {'-'*14}  {'-'*10}  {'-'*6}  {'-'*8}  {'-'*9}")
for label, a, ecc, inc in orbits:
    r = poliastro_orbit(a=a, ecc=ecc, inc=inc, raan=0.0, argp=0.0, nu=0.0)
    print(f"  {label:14s}  {a/1e3:10.1f}  {ecc:6.4f}  "
          f"{r['period'].to("min")}  {r['v_mag']}")


# ── 2. Hohmann transfers ──────────────────────────────────────────────────────
print(f"\n[2] Hohmann transfers")

transfers = [
    ("LEO 200km -> GEO",       R_E + 200e3,  42164e3),
    ("LEO 200km -> Moon dist", R_E + 200e3,  384400e3),
    ("LEO 400km -> LEO 600km", R_E + 400e3,  R_E + 600e3),
]

print(f"  {'Transfer':28s}  {'dv1 (m/s)':>10s}  {'dv2 (m/s)':>10s}  "
      f"{'total (m/s)':>11s}  {'TOF (h)':>8s}")
print(f"  {'-'*28}  {'-'*10}  {'-'*10}  {'-'*11}  {'-'*8}")
for label, a_i, a_f in transfers:
    r = poliastro_hohmann(a_i=a_i, a_f=a_f)
    print(f"  {label:28s}  {r['dv_1']}  {r['dv_2']}  "
          f"  {r['dv_total']}  {r['t_transfer'].to("hr")}")


# ── 3. Orbit System -- chain with propellant_mass RSQ ────────────────────────
print(f"\n[3] LEO->GEO mission budget (orbit + propellant_mass in one System)")

register()   # push adapters to global registry so sys.use() can find them

mission = anvil.system("leo_geo_mission")
mission.add("a_i",   R_E + 200e3, "m",   desc="Departure orbit radius")
mission.add("a_f",   42164e3,     "m",   desc="Target orbit radius (GEO)")
mission.add("Isp",   450.0,       "s",   desc="Engine specific impulse")
mission.add("m_wet", 5000.0,      "kg",  desc="Spacecraft wet mass")
mission.add("g0",    9.80665,     "m/s^2")

mission.use(poliastro_hohmann)          # Adapter object directly (not registry lookup)

def rocket_budget(dv_total, Isp, g0, m_wet):
    """Tsiolkovsky: given m_wet, compute propellant and dry mass."""
    mr = math.exp(dv_total / (Isp * g0))
    m_prop = m_wet * (1.0 - 1.0 / mr)
    return {"m_prop": Q(m_prop, "kg"), "m_dry": Q(m_wet - m_prop, "kg"), "mass_ratio": mr}
mission.use(rocket_budget)

result = mission.solve_forward()
result.summary(keys=["a_i", "a_f", "dv_total", "t_transfer", "m_prop", "m_dry"])

print(f"\n  Total dv   = {result['dv_total'].to("km/s")}")
print(f"  Transfer   = {result['t_transfer'].to("hr")}")
print(f"  Propellant = {result['m_prop']}  "
      f"({result['m_prop'].value / 5000.0 * 100:.1f}% of wet mass)")
print(f"  Dry mass   = {result['m_dry']}")


# ── 4. Sweep: transfer dv vs target altitude ──────────────────────────────────
print(f"\n[4] Sweep: transfer dv vs target altitude (100 km to 42 164 km)")

altitudes_km = np.linspace(100, 42164, 8)
print(f"  {'Alt (km)':>10s}  {'dv_total (m/s)':>15s}  {'TOF (h)':>8s}")
print(f"  {'-'*10}  {'-'*15}  {'-'*8}")
for alt in altitudes_km:
    r = poliastro_hohmann(a_i=R_E + 200e3, a_f=R_E + alt * 1e3)
    print(f"  {alt:10.0f}  {r['dv_total']}  "
          f"{r['t_transfer'].to("hr")}")


# ── 5. Sensitivity analysis ───────────────────────────────────────────────────
print(f"\n[5] Sensitivity: what drives orbital speed in LEO?")

leo_sys = anvil.system("leo_orbit")
leo_sys.add("a",    R_E + 400e3, "m")
leo_sys.add("ecc",  0.0)
leo_sys.add("inc",  math.radians(51.6), "rad")
leo_sys.add("raan", 0.0, "rad")
leo_sys.add("argp", 0.0, "rad")
leo_sys.add("nu",   0.0, "rad")
leo_sys.use(poliastro_orbit)            # Adapter object directly

sens = leo_sys.sensitivity(outputs=["v_mag", "period"])
print(f"\n  Top drivers of orbital speed (v_mag):")
for inp, val in sens.top("v_mag", n=4):
    print(f"    {inp:8s}  {val:+.4f}")

print(f"\n  Top drivers of orbital period:")
for inp, val in sens.top("period", n=4):
    print(f"    {inp:8s}  {val:+.4f}")


# ── 6. Propagation checks ─────────────────────────────────────────────────────
print(f"\n[6] Propagation checks (circular LEO, 400 km)")

a0 = R_E + 400e3
T_s = poliastro_orbit(a=a0, ecc=0.0, inc=0.0, raan=0.0, argp=0.0, nu=0.0)
T   = T_s["period"].si

print(f"  Orbital period = {T/60:.2f} min")
print(f"  {'Fraction':12s}  {'nu_f (deg)':>12s}  {'r_mag (km)':>12s}")
print(f"  {'-'*12}  {'-'*12}  {'-'*12}")
for frac, label in [(0.25, "T/4"), (0.5, "T/2"), (1.0, "T")]:
    r = poliastro_propagate(a=a0, ecc=0.0, inc=0.0, raan=0.0,
                             argp=0.0, nu=0.0, dt=T * frac)
    r_km = math.sqrt(r["r_x"].si**2 + r["r_y"].si**2 + r["r_z"].si**2) / 1e3
    print(f"  {label:12s}  {math.degrees(r['nu_f'].si):12.2f}  {r_km:12.1f}")


# ── 7. Eccentric orbit: GTO propagation ──────────────────────────────────────
print(f"\n[7] GTO propagation -- quarter period from perigee")

# GTO: 200 km x 35786 km
a_gto  = (R_E + 200e3 + 42164e3) / 2
ecc_gto = (42164e3 - (R_E + 200e3)) / (42164e3 + R_E + 200e3)
T_gto = poliastro_orbit(a=a_gto, ecc=ecc_gto, inc=0.0,
                         raan=0.0, argp=0.0, nu=0.0)["period"].si

print(f"  a_gto   = {a_gto/1e6:.3f} Mm,  ecc = {ecc_gto:.4f}")
print(f"  r_p     = {(R_E + 200e3)/1e6:.3f} Mm (perigee)")
print(f"  r_a     = {42164e3/1e6:.3f} Mm (apogee)")
print(f"  period  = {T_gto/3600:.2f} h")

rp = poliastro_propagate(a=a_gto, ecc=ecc_gto, inc=0.0,
                          raan=0.0, argp=0.0, nu=0.0,
                          dt=T_gto / 2)
r_apo = math.sqrt(rp["r_x"].si**2 + rp["r_y"].si**2 + rp["r_z"].si**2)
print(f"\n  After T/2 (at apogee):")
print(f"  r_mag   = {r_apo/1e6:.3f} Mm  (expect {42164e3/1e6:.3f} Mm)")

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
