"""
Example 22: pykep Adapter -- Trajectory Design in Anvil
========================================================

Demonstrates the pykep adapter for Lambert arc solutions, Keplerian
propagation, and planet ephemerides -- all integrated into Anvil Systems
and sweeps.

pykep_lambert REQUIRES pykep installed.
pykep_propagate and pykep_planet_state work in mock mode without it.

PREREQUISITES:
    pip install pykep    (required for Lambert sections)

WHAT THIS EXAMPLE DOES:
    1. Planet state at J2000 and at a future epoch
    2. Propagate Earth's state by one year (verify closure)
    3. Lambert arc Earth->Mars at J2000 positions (pykep required)
    4. Delta-v budget System: planet state + Lambert in one solve
    5. Sweep: tof scan for Earth->Mars (mini porkchop column)
    6. Combining poliastro + pykep: LEO departure + interplanetary arc
"""

import sys
import os
import math
import numpy as np


import anvil
from anvil import Q

from anvil.adapters.pykep_trajectories import (
    pykep_lambert, pykep_propagate, pykep_planet_state, register
)
from anvil.adapters.poliastro_orbits import poliastro_hohmann

W      = 64
AU     = 1.495978707e11
MU_SUN = 1.32712440018e20

print("=" * W)
print("  Example 22: pykep Adapter")
print("=" * W)

HAS_PYKEP = False
try:
    import pykep
    HAS_PYKEP = True
    print(f"  pykep {pykep.__version__} found.")
except ImportError:
    print("  pykep not installed.  Lambert sections will be skipped.")
    print("  Install: pip install pykep")

print()


# ── 1. Planet states ──────────────────────────────────────────────────────────
print("[1] Planet states at J2000 (epoch = 0 MJD2000)")

planets = ["mercury", "venus", "earth", "mars", "jupiter"]
print(f"  {'Planet':10s}  {'|r| (AU)':>10s}  {'|v| (km/s)':>12s}")
print(f"  {'-'*10}  {'-'*10}  {'-'*12}")
for planet in planets:
    r = pykep_planet_state(planet=planet, epoch_mjd2000=0.0)
    print(f"  {planet:10s}  {r['r_mag'].value / AU:10.4f}  "
          f"{r['v_mag'].value / 1e3:12.3f}")


# ── 2. Propagate Earth 1 year -- closure check ───────────────────────────────
print(f"\n[2] Propagate Earth state by 1 year (expect |r| ~ 1 AU at end)")

r_e0 = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
r_e1 = pykep_propagate(
    r_x=r_e0["r_x"].si, r_y=r_e0["r_y"].si, r_z=r_e0["r_z"].si,
    v_x=r_e0["v_x"].si, v_y=r_e0["v_y"].si, v_z=r_e0["v_z"].si,
    dt=365.25 * 86400,
    mu=MU_SUN,
)
print(f"  |r| at t=0   : {r_e0['r_mag'].value / AU:.5f} AU")
print(f"  |r| at t=1yr : {r_e1['r_mag_f'].value / AU:.5f} AU  (expect ~1.00000)")

# Cross-check: Earth state 1 year later from ephemeris
r_e1_eph = pykep_planet_state(planet="earth", epoch_mjd2000=365.25)
dr = math.sqrt(
    (r_e1["r_x_f"].si - r_e1_eph["r_x"].si)**2 +
    (r_e1["r_y_f"].si - r_e1_eph["r_y"].si)**2 +
    (r_e1["r_z_f"].si - r_e1_eph["r_z"].si)**2
)
print(f"  Closure error : {dr/AU:.4f} AU  (mock: mean elements; pykep: JPL ephemeris)")


# ── 3. Lambert arc Earth->Mars ────────────────────────────────────────────────
print(f"\n[3] Lambert arc Earth->Mars at J2000 positions, tof=200 days")

if not HAS_PYKEP:
    print("  [skipped -- pykep not installed]")
else:
    r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
    r_mars  = pykep_planet_state(planet="mars",  epoch_mjd2000=200.0)  # Mars 200 days later

    sol = pykep_lambert(
        r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
        r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,  r1_z=r_mars["r_z"].si,
        tof=200 * 86400,
    )
    print(f"  Departure v   : ({sol['v_dep_x'].value/1e3:.3f}, "
          f"{sol['v_dep_y'].value/1e3:.3f}, {sol['v_dep_z'].value/1e3:.3f}) km/s")
    print(f"  Arrival v     : ({sol['v_arr_x'].value/1e3:.3f}, "
          f"{sol['v_arr_y'].value/1e3:.3f}, {sol['v_arr_z'].value/1e3:.3f}) km/s")
    print(f"  |v_dep|       : {sol['dv_dep'].value/1e3:.3f} km/s")
    print(f"  |v_arr|       : {sol['dv_arr'].value/1e3:.3f} km/s")

    # Verify arc: propagate departure state forward tof
    r_check = pykep_propagate(
        r_x=r_earth["r_x"].si, r_y=r_earth["r_y"].si, r_z=r_earth["r_z"].si,
        v_x=sol["v_dep_x"].si, v_y=sol["v_dep_y"].si, v_z=sol["v_dep_z"].si,
        dt=200 * 86400, mu=MU_SUN,
    )
    err_m = math.sqrt(
        (r_check["r_x_f"].si - r_mars["r_x"].si)**2 +
        (r_check["r_y_f"].si - r_mars["r_y"].si)**2 +
        (r_check["r_z_f"].si - r_mars["r_z"].si)**2
    )
    print(f"  Arc closure   : {err_m/1e3:.3f} km  (should be ~0)")


# ── 4. Delta-v budget System: planet state + Lambert ─────────────────────────
print(f"\n[4] Delta-v budget System (planet state + Lambert in one solve)")

if not HAS_PYKEP:
    print("  [skipped -- pykep not installed]")
else:
    register()  # push pykep adapters to global registry

    traj = anvil.system("earth_mars_transfer")
    traj.add("epoch_dep", 0.0,        desc="Departure epoch (MJD2000 days)")
    traj.add("tof",       200.0 * 86400, "s", desc="Time of flight")

    # Earth departure state
    def earth_state(epoch_dep):
        return pykep_planet_state(planet="earth", epoch_mjd2000=epoch_dep)
    traj.use(earth_state)

    # Mars arrival state (epoch_dep + tof)
    def mars_arrival(epoch_dep, tof):
        return pykep_planet_state(
            planet="mars",
            epoch_mjd2000=epoch_dep + tof / 86400
        )
    traj.use(mars_arrival, outputs={"r_x": "r_x_m", "r_y": "r_y_m", "r_z": "r_z_m",
                                      "v_x": "v_x_m", "v_y": "v_y_m", "v_z": "v_z_m",
                                      "r_mag": "r_mag_m", "v_mag": "v_mag_m"})

    # Lambert
    def lambert_transfer(r_x, r_y, r_z, r_x_m, r_y_m, r_z_m, tof):
        return pykep_lambert(
            r0_x=r_x, r0_y=r_y, r0_z=r_z,
            r1_x=r_x_m, r1_y=r_y_m, r1_z=r_z_m,
            tof=tof,
        )
    traj.use(lambert_transfer)

    res = traj.solve_forward()
    print(f"  Departure  : epoch {res['epoch_dep']}")
    print(f"  TOF        : {res['tof'].si / 86400:.1f} days")
    print(f"  dv_dep     : {res['dv_dep'].value/1e3:.3f} km/s")
    print(f"  dv_arr     : {res['dv_arr'].value/1e3:.3f} km/s")
    print(f"  dv_total   : {res['dv_total'].value/1e3:.3f} km/s")


# ── 5. Sweep: tof scan (mini porkchop column) ─────────────────────────────────
print(f"\n[5] TOF sweep (Earth->Mars, 100-350 days) -- departure at J2000")

if not HAS_PYKEP:
    print("  [skipped -- pykep not installed]")
else:
    r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
    tofs_days = np.linspace(100, 350, 6)

    print(f"  {'TOF (days)':>10s}  {'dv_dep (km/s)':>14s}  "
          f"{'dv_arr (km/s)':>14s}  {'dv_total (km/s)':>16s}")
    print(f"  {'-'*10}  {'-'*14}  {'-'*14}  {'-'*16}")
    for tof_d in tofs_days:
        r_mars = pykep_planet_state(planet="mars", epoch_mjd2000=tof_d)
        try:
            s = pykep_lambert(
                r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si,
                r0_z=r_earth["r_z"].si,
                r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,
                r1_z=r_mars["r_z"].si,
                tof=tof_d * 86400,
            )
            print(f"  {tof_d:10.0f}  {s['dv_dep'].value/1e3:14.3f}  "
                  f"{s['dv_arr'].value/1e3:14.3f}  {s['dv_total'].value/1e3:16.3f}")
        except Exception as e:
            print(f"  {tof_d:10.0f}  {'error: '+str(e)[:40]}")


# ── 6. Combined: LEO departure + interplanetary arc ───────────────────────────
print(f"\n[6] Complete mission: LEO parking + escape + interplanetary arc")
print(f"    (poliastro Hohmann for escape burn, pykep Lambert for arc)")

if not HAS_PYKEP:
    print("  [skipped -- pykep not installed]")
else:
    R_E = 6371e3
    MU_E = 3.986004418e14
    V_EARTH_HELIO = r_earth["v_mag"].si   # Earth's heliocentric speed

    # Lambert departure velocity vector magnitude at Earth
    r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
    r_mars_200 = pykep_planet_state(planet="mars", epoch_mjd2000=200.0)
    sol = pykep_lambert(
        r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
        r1_x=r_mars_200["r_x"].si, r1_y=r_mars_200["r_y"].si,
        r1_z=r_mars_200["r_z"].si,
        tof=200 * 86400,
    )

    # Hyperbolic excess velocity at Earth departure
    v_dep = sol["dv_dep"].si      # heliocentric departure speed (m/s)
    v_inf = abs(v_dep - V_EARTH_HELIO)   # rough estimate (assumes co-linear)

    # Escape dv from 200 km LEO: v_esc^2 = v_circ^2 + v_inf^2
    # v_park = sqrt(mu/r), v_hyp = sqrt(v_park^2 + v_inf^2)
    r_park = R_E + 200e3
    v_park = math.sqrt(MU_E / r_park)
    v_hyp  = math.sqrt(v_park**2 + v_inf**2)
    dv_escape = v_hyp - v_park

    print(f"  Earth heliocentric speed  : {V_EARTH_HELIO/1e3:.3f} km/s")
    print(f"  Lambert departure speed   : {v_dep/1e3:.3f} km/s")
    print(f"  Hyperbolic excess v_inf   : {v_inf/1e3:.3f} km/s  (co-linear approx)")
    print(f"  LEO circular speed (200km): {v_park/1e3:.3f} km/s")
    print(f"  Escape burn dv            : {dv_escape/1e3:.3f} km/s")
    print(f"  Lambert arc total dv      : {sol['dv_total'].value/1e3:.3f} km/s")
    print(f"  Dominant cost: escape burn from LEO to interplanetary")

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
