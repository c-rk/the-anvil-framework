"""
Example: Orifice Pressure Solver
=================================

Given phi, gas names, orifice size range, and per-line P0 bounds,
find the optimal orifice diameters and pressure setpoints.

User inputs:
    phi            -- target equivalence ratio
    fuel_gas       -- Anvil fluids DB key, e.g. "hydrogen"
    ox_gas         -- Anvil fluids DB key, e.g. "oxygen"
    fuel_formula   -- chemical formula, e.g. "H2"
    orifice_range  -- (d_min_mm, d_max_mm)  continuous search window
    P0_bounds      -- {"fuel": (lo_Pa, hi_Pa), "ox": (lo_Pa, hi_Pa)}

Gas properties are fetched from the Anvil fluids DB automatically.
Orifice sizes and P0 settings are solved jointly by sys.optimize().
"""

import sys
import os
import math
import re
import numpy as np


import anvil
from anvil import Q
from anvil.db import fluids


# =============================================================================
# Stoichiometry helper  (not an RSQ -- takes string inputs)
# =============================================================================

def _stoich_FO(fuel_formula, oxidizer="O2"):
    """Stoichiometric (F/O) mass ratio for CxHy fuel."""
    _AW = {"H": 1.008, "C": 12.011, "O": 15.999, "N": 14.007}
    _OX = {"o2": (31.999, 1.00), "air": (28.970, 0.21)}
    a = {e: int(n or 1)
         for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", fuel_formula) if e}
    n_O2 = a.get("C", 0) + a.get("H", 0) / 4 - a.get("O", 0) / 2
    mw_f = sum(_AW.get(e, 0) * n for e, n in a.items())
    MW_ox, x_O2 = _OX.get(oxidizer.lower(), (mw_f, 1.0))
    return mw_f / ((n_O2 / x_O2) * MW_ox)


# =============================================================================
# RSQ definitions  -- each function is self-contained so it serialises safely
# into the project registry (registry stores source only, not module context)
# =============================================================================

def ox_choked_flow(P0_O2, T0_O2, d_O2, gamma_O2, R_O2, Cd_O2=0.61):
    """Choked flow through the oxidizer orifice (d_O2 in mm)."""
    import math
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    g  = si(gamma_O2)
    Gm = math.sqrt(g) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    K  = si(Cd_O2) * math.pi * (si(d_O2) * 5e-4) ** 2 * Gm / math.sqrt(si(R_O2) * si(T0_O2))
    return {"mdot_O2": Q(K * si(P0_O2), "kg/s"), "K_O2": K}


def phi_to_fuel_mdot(mdot_O2, phi, stoich_FO_val):
    """Fuel mdot for target equivalence ratio."""
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    return {"mdot_fuel": Q(si(phi) * si(stoich_FO_val) * si(mdot_O2), "kg/s")}


def fuel_P0_required(mdot_fuel, T0_fuel, d_fuel, gamma_fuel, R_fuel, Cd_fuel=0.61):
    """P0 required to deliver mdot_fuel through fuel orifice (d_fuel in mm)."""
    import math
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    g  = si(gamma_fuel)
    Gm = math.sqrt(g) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    K  = si(Cd_fuel) * math.pi * (si(d_fuel) * 5e-4) ** 2 * Gm / math.sqrt(si(R_fuel) * si(T0_fuel))
    return {"P0_fuel": Q(si(mdot_fuel) / K, "Pa"), "K_fuel": K}


def pressure_margin(P0_O2, P0_fuel, P0_O2_min, P0_O2_max, P0_fuel_min, P0_fuel_max):
    """
    Minimum pressure margin across both lines with per-line bounds (Pa).
    Positive = both lines inside bounds.  Maximised by the optimizer.
    """
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    return {"min_slack": Q(min(
        si(P0_O2)   - si(P0_O2_min),  si(P0_O2_max)   - si(P0_O2),
        si(P0_fuel) - si(P0_fuel_min), si(P0_fuel_max) - si(P0_fuel),
    ), "Pa")}


# =============================================================================
# Project registry
# =============================================================================

proj = anvil.project("orifice_phi_study", path="./orifice_phi_work")

for fn, desc in [
    (ox_choked_flow,   "Choked flow through the oxidizer orifice"),
    (phi_to_fuel_mdot, "Required fuel mdot for target equivalence ratio"),
    (fuel_P0_required, "Required P0 for fuel line at target mass flow"),
    (pressure_margin,  "Min pressure margin across both lines (optimizer objective)"),
]:
    proj.push(fn, domain="flow.orifice.phi", description=desc,
              tags=["orifice", "choked", "phi"])


# =============================================================================
# System builder  (gas properties fetched from the Anvil fluids DB)
# =============================================================================

def _build_system(fuel_gas, ox_gas, T0=300.0, Cd=0.61):
    gf = fluids.get(fuel_gas, T=T0)
    go = fluids.get(ox_gas,   T=T0)
    s  = anvil.system("phi_solver")
    s.add("P0_O2",       1e6,                    "Pa")
    s.add("T0_O2",       T0,                     "K")
    s.add("d_O2",        1.0)
    s.add("gamma_O2",    float(go["gamma"]))
    s.add("R_O2",        float(go["R_gas"].si),  "J/kg/K")
    s.add("Cd_O2",       Cd)
    s.add("phi",         1.0)
    s.add("stoich_FO_val", 0.1)
    s.add("T0_fuel",     T0,                     "K")
    s.add("d_fuel",      1.0)
    s.add("gamma_fuel",  float(gf["gamma"]))
    s.add("R_fuel",      float(gf["R_gas"].si),  "J/kg/K")
    s.add("Cd_fuel",     Cd)
    s.add("P0_O2_min",   3e5,   "Pa")
    s.add("P0_O2_max",   20e5,  "Pa")
    s.add("P0_fuel_min", 3e5,   "Pa")
    s.add("P0_fuel_max", 20e5,  "Pa")
    s.use(proj.R.ox_choked_flow)
    s.use(proj.R.phi_to_fuel_mdot)
    s.use(proj.R.fuel_P0_required)
    s.use(proj.R.pressure_margin)
    return s


# =============================================================================
# Solver  (single sys.optimize() over P0_O2, d_fuel, d_O2 jointly)
# =============================================================================

def find_pressure_settings(phi, fuel_gas, ox_gas, fuel_formula,
                            orifice_range, P0_bounds,
                            oxidizer_formula="O2", T0=300.0, Cd=0.61):
    """
    Find optimal orifice sizes and P0 setpoints for a target phi.

    Parameters
    ----------
    phi : float
        Target equivalence ratio.
    fuel_gas, ox_gas : str
        Anvil fluids DB keys, e.g. "hydrogen", "oxygen".
    fuel_formula : str
        Chemical formula for stoichiometry, e.g. "H2", "CH4".
    orifice_range : (float, float)
        (d_min_mm, d_max_mm) -- continuous search window for both orifices.
    P0_bounds : dict
        {"fuel": (lo_Pa, hi_Pa), "ox": (lo_Pa, hi_Pa)} -- per-line limits.
    oxidizer_formula : str
        "O2" (default) or "air".

    Returns
    -------
    dict with keys d_fuel, d_ox, P0_fuel, P0_ox, mdot_fuel, mdot_ox, margin
    (pressures in bar, flows in g/s, diameters in mm).
    None if no feasible solution exists within the given bounds.
    """
    s = _build_system(fuel_gas, ox_gas, T0, Cd)
    s.set(
        phi=phi,
        stoich_FO_val=_stoich_FO(fuel_formula, oxidizer_formula),
        P0_O2_min=P0_bounds["ox"][0],    P0_O2_max=P0_bounds["ox"][1],
        P0_fuel_min=P0_bounds["fuel"][0], P0_fuel_max=P0_bounds["fuel"][1],
    )

    opt = s.optimize(
        objective="min_slack",
        design_vars={
            "P0_O2":  P0_bounds["ox"],
            "d_O2":   orifice_range,
            "d_fuel": orifice_range,
        },
        minimize=False,
        method="differential_evolution",
        seed=0, maxiter=500, tol=1e-4,
    )

    # opt.success may be False if convergence tolerance not met, but the
    # optimizer still records the best feasible point found. Check opt.fun
    # (the actual min_slack at best point) rather than convergence status.
    if not math.isfinite(opt.fun) or opt.fun <= 0:
        return None

    return {
        "d_fuel":    round(opt.x["d_fuel"], 4),
        "d_ox":      round(opt.x["d_O2"],   4),
        "P0_fuel":   float(opt["P0_fuel"].si) / 1e5,
        "P0_ox":     opt.x["P0_O2"] / 1e5,
        "mdot_fuel": float(opt["mdot_fuel"].si) * 1e3,
        "mdot_ox":   float(opt["mdot_O2"].si) * 1e3,
        "margin":    opt.fun / 1e5,
    }


# =============================================================================
# Usage
# =============================================================================

W = 64
print("=" * W)
print("  Orifice Pressure Solver")
print("=" * W)

# ── Single solve ──────────────────────────────────────────────────────────────
print("\n[1] H2/O2  phi=1.0  |  orifice 0.5-2.0 mm  |  both lines 3-20 bar")

r = find_pressure_settings(
    phi=1.0,
    fuel_gas="hydrogen",
    ox_gas="oxygen",
    fuel_formula="H2",
    orifice_range=(0.5, 2.0),
    P0_bounds={"fuel": (3e5, 20e5), "ox": (3e5, 20e5)},
)
if r:
    print(f"  d_fuel  = {r['d_fuel']:.3f} mm     d_ox    = {r['d_ox']:.3f} mm")
    print(f"  P0_fuel = {r['P0_fuel']:.3f} bar    P0_ox   = {r['P0_ox']:.3f} bar")
    print(f"  mdot_fuel = {r['mdot_fuel']:.4f} g/s   mdot_ox = {r['mdot_ox']:.4f} g/s")
    print(f"  margin  = {r['margin']:.4f} bar")

# ── phi sweep ─────────────────────────────────────────────────────────────────
print(f"\n[2] phi sweep  (0.5 to 2.5)")
print(f"  {'phi':>6}  {'d_fuel':>8}  {'d_ox':>6}  "
      f"{'P0_fuel':>10}  {'P0_ox':>8}  {'margin':>8}")
print(f"  {'-'*6}  {'-'*8}  {'-'*6}  {'-'*10}  {'-'*8}  {'-'*8}")

for phi_val in np.linspace(0.5, 2.5, 9):
    r = find_pressure_settings(
        phi=phi_val,
        fuel_gas="hydrogen", ox_gas="oxygen", fuel_formula="H2",
        orifice_range=(0.5, 2.0),
        P0_bounds={"fuel": (3e5, 20e5), "ox": (3e5, 20e5)},
    )
    if r:
        print(f"  {phi_val:>6.2f}  {r['d_fuel']:>8.3f}  {r['d_ox']:>6.3f}  "
              f"  {r['P0_fuel']:>8.3f}  {r['P0_ox']:>8.3f}  {r['margin']:>8.4f}")
    else:
        print(f"  {phi_val:>6.2f}  {'-- no feasible solution --':>42}")

# ── asymmetric bounds ─────────────────────────────────────────────────────────
print(f"\n[3] Asymmetric bounds: H2 regulator 3-10 bar,  O2 regulator 3-20 bar")

r = find_pressure_settings(
    phi=1.0,
    fuel_gas="hydrogen", ox_gas="oxygen", fuel_formula="H2",
    orifice_range=(0.5, 2.0),
    P0_bounds={"fuel": (3e5, 10e5), "ox": (3e5, 20e5)},
)
if r:
    print(f"  d_fuel  = {r['d_fuel']:.3f} mm     d_ox    = {r['d_ox']:.3f} mm")
    print(f"  P0_fuel = {r['P0_fuel']:.3f} bar    P0_ox   = {r['P0_ox']:.3f} bar")
    print(f"  margin  = {r['margin']:.4f} bar")

# ── CH4 / O2 ─────────────────────────────────────────────────────────────────
print(f"\n[4] CH4/O2  phi=0.8  |  orifice 0.5-3.0 mm  |  5-25 bar")

r = find_pressure_settings(
    phi=0.8,
    fuel_gas="methane", ox_gas="oxygen", fuel_formula="CH4",
    orifice_range=(0.5, 3.0),
    P0_bounds={"fuel": (5e5, 25e5), "ox": (5e5, 25e5)},
)
if r:
    print(f"  d_fuel  = {r['d_fuel']:.3f} mm     d_ox    = {r['d_ox']:.3f} mm")
    print(f"  P0_fuel = {r['P0_fuel']:.3f} bar    P0_ox   = {r['P0_ox']:.3f} bar")
    print(f"  margin  = {r['margin']:.4f} bar")

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
