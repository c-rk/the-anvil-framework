"""
Example 3: LEO to GEO Orbital Transfer Mission
===============================================

Demonstrates:
    - Using built-in orbital mechanics RSQs
    - Composition: combining multiple Relations into a mission plan
    - Direct function calls + System integration
    - Working with large SI values (orbital radii, velocities)

Engineering context:
    Plan a Hohmann transfer from Low Earth Orbit (LEO) to
    Geostationary Orbit (GEO). Compute delta-V budget, transfer
    time, and propellant mass using the Tsiolkovsky equation.
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 3: LEO to GEO Orbital Transfer")
print("=" * 60)

# --- Constants ---
mu_earth = 3.986004418e14   # m^3/s^2
R_earth  = 6371e3           # m

# --- Step 1: Define the orbits ---
h_LEO = 400e3    # 400 km altitude
h_GEO = 35786e3  # geostationary altitude

r_LEO = R_earth + h_LEO
r_GEO = R_earth + h_GEO

print(f"\n[1] Orbit definitions:")
print(f"  LEO: {h_LEO/1e3:.0f} km altitude, r = {r_LEO/1e3:.0f} km")
print(f"  GEO: {h_GEO/1e3:.0f} km altitude, r = {r_GEO/1e3:.0f} km")

# --- Step 2: Orbital velocities ---
print(f"\n[2] Orbital velocities:")
leo_v = anvil.R.vis_viva(mu=mu_earth, r=r_LEO, a=r_LEO)
geo_v = anvil.R.vis_viva(mu=mu_earth, r=r_GEO, a=r_GEO)
print(f"  V_LEO = {leo_v['V_orbital'].to("km/s")}")
print(f"  V_GEO = {geo_v['V_orbital'].to("km/s")}")

# --- Step 3: Hohmann transfer ---
print(f"\n[3] Hohmann transfer:")
transfer = anvil.R.hohmann_transfer(mu=mu_earth, r1=r_LEO, r2=r_GEO)
print(f"  dV1 (LEO departure):  {transfer['dv1'].to("km/s")}")
print(f"  dV2 (GEO insertion):  {transfer['dv2'].to("km/s")}")
print(f"  Total delta-V:        {transfer['dv_total'].to("km/s")}")
print(f"  Transfer time:        {transfer['tof'].value / 3600:.2f} hours")

# --- Step 4: Orbital periods ---
print(f"\n[4] Orbital periods:")
T_LEO = anvil.R.orbital_period(mu=mu_earth, a=r_LEO)
T_GEO = anvil.R.orbital_period(mu=mu_earth, a=r_GEO)
print(f"  LEO period: {T_LEO['T_orbital'].value / 60:.1f} min")
print(f"  GEO period: {T_GEO['T_orbital'].value / 3600:.2f} hrs (should be ~24)")

# --- Step 5: Propellant budget using Tsiolkovsky ---
print(f"\n[5] Propellant budget (bipropellant engine, Isp = 320 s):")

# Build a mission system
mission = System("leo_to_geo")
mission.add("mu",         mu_earth)
mission.add("r_LEO",      r_LEO,   "m")
mission.add("r_GEO",      r_GEO,   "m")
mission.add("Isp_engine",  320,     "s",    desc="Engine specific impulse")
mission.add("m_payload",   2000,    "kg",   desc="Payload mass")
mission.add("m_structure",  500,    "kg",   desc="Structure mass (dry)")

# Delta-V
mission.use("hohmann_transfer", map={"r1": "r_LEO", "r2": "r_GEO"})

# Propellant mass from Tsiolkovsky (inverted)
def propellant_mass(dv_total, Isp_engine, m_payload, m_structure):
    """Compute propellant mass from delta-V requirement."""
    g0 = 9.80665
    Ve = Isp_engine * g0
    mass_ratio = np.exp(dv_total / Ve)
    m_dry = m_payload + m_structure
    m_wet = m_dry * mass_ratio
    m_propellant = m_wet - m_dry
    return {
        "mass_ratio": mass_ratio,
        "m_propellant": Q(m_propellant, "kg"),
        "m_wet": Q(m_wet, "kg"),
    }

mission.use(propellant_mass)
result = mission.solve_forward()

print(f"  Mass ratio:     {result['mass_ratio'].si:.2f}")
print(f"  Propellant:     {result['m_propellant']}")
print(f"  Wet mass:       {result['m_wet']}")
print(f"  Payload frac:   {2000 / result['m_wet'].si:.1%}")

# --- Step 6: Sweep over engine Isp ---
print(f"\n[6] Sweep: propellant mass vs engine Isp...")
sweep = mission.sweep("Isp_engine", np.linspace(250, 450, 5))
sweep.summary(outputs=["m_propellant", "mass_ratio", "m_wet"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
