"""
Example 16: Global Optimization and System.optimize()
======================================================

Demonstrates:
    - solvers.minimize_global() with all four methods
    - System.optimize() for engineering design optimization
    - Maximizing thrust by tuning nozzle geometry
    - Comparing global vs gradient-based methods
    - Reading OptimizeResult fields and subscripting

Engineering context:
    Given a fixed propellant and chamber conditions, find the exit area
    and throat area that maximize specific impulse while respecting
    a mass flow constraint. Then extend to a 3-variable nozzle study.
"""

import sys, os
import numpy as np

import anvil
from anvil import solvers, Q

print("=" * 60)
print("  Example 16: Optimization")
print("=" * 60)


# --------------------------------------------------------------
# Part 1: minimize_global — direct function optimization
# --------------------------------------------------------------
print("\n[1] Direct global optimization: Himmelblau's function")
print("    f(x,y) = (x²+y-11)² + (x+y²-7)²  has 4 global minima at f=0")

def himmelblau(x):
    return (x[0]**2 + x[1] - 11)**2 + (x[0] + x[1]**2 - 7)**2

bounds = [(-5, 5), (-5, 5)]

for method in ["differential_evolution", "dual_annealing", "shgo", "basinhopping"]:
    r = solvers.minimize_global(himmelblau, bounds, method=method, seed=0)
    status = "OK" if r["fun"] < 1e-6 else "MISSED"
    print(f"  {method:28s}  f={r['fun']:.2e}  x=[{r['x'][0]:+.4f}, {r['x'][1]:+.4f}]  [{status}]")

# --------------------------------------------------------------
# Part 2: System.optimize() — nozzle thrust maximization
# --------------------------------------------------------------
print("\n[2] System.optimize(): maximize nozzle thrust")
print("    Design variables: A_throat, A_exit")
print("    Fixed: chamber conditions, ambient pressure")

nozzle = anvil.S.rocket_nozzle.copy()

# Fix chamber conditions and ambient
nozzle.set(
    P0=8e6,       # 8 MPa
    T0=3200,      # K
    gamma=1.25,
    R_gas=400.0,  # J/kg/K
    P_amb=101325,
)

# Maximize thrust by sizing throat and exit
opt = nozzle.optimize(
    objective="thrust",
    design_vars={
        "A_throat": (0.002, 0.030),   # 20 to 300 cm²
        "A_exit":   (0.010, 0.300),   # 100 to 3000 cm²
    },
    minimize=False,
    method="differential_evolution",
    seed=42,
    maxiter=80,
    verbose=False,
)

print(f"\n  Status : {'CONVERGED' if opt.success else 'NOT CONVERGED'}")
print(f"  Evals  : {opt.nfev}")
print(f"  Thrust : {opt.fun/1000:.2f} kN  ({opt.fun:.0f} N)")
print(f"  A_throat: {opt.x['A_throat']*1e4:.1f} cm²")
print(f"  A_exit  : {opt.x['A_exit']*1e4:.1f} cm²")
print(f"  Area ratio: {opt.x['A_exit'] / opt.x['A_throat']:.1f}")

# Access other quantities from the optimal result
print(f"\n  Other results at optimum:")
print(f"    Isp    : {float(opt['Isp'].value):.1f} s")
print(f"    M_exit : {float(opt['M_exit'].value):.2f}")
print(f"    mdot   : {float(opt['mdot'].value):.3f} kg/s")
print(f"    V_exit : {opt['V_exit'].to('km/s')}")

# --------------------------------------------------------------
# Part 3: Maximize Isp (efficiency) — different objective
# --------------------------------------------------------------
print("\n[3] Same system, different objective: maximize Isp")

opt_isp = nozzle.optimize(
    objective="Isp",
    design_vars={
        "A_throat": (0.002, 0.030),
        "A_exit":   (0.010, 0.300),
    },
    minimize=False,
    method="differential_evolution",
    seed=42,
    maxiter=80,
    verbose=False,
)

print(f"  Isp    : {opt_isp.fun:.1f} s")
print(f"  Thrust : {float(opt_isp['thrust'].value)/1000:.2f} kN")
print(f"  A_throat: {opt_isp.x['A_throat']*1e4:.1f} cm²")
print(f"  A_exit  : {opt_isp.x['A_exit']*1e4:.1f} cm²  (-> area ratio {opt_isp.x['A_exit']/opt_isp.x['A_throat']:.1f})")
print("  (Higher Isp favours large expansion ratio; thrust trades off mdot vs Ve)")

# --------------------------------------------------------------
# Part 4: Custom system — optimize a heat exchanger NTU
# --------------------------------------------------------------
print("\n[4] Custom system: optimal NTU for heat exchanger effectiveness")

hx = anvil.system("hx_opt")
hx.add("NTU",    2.0)    # number of transfer units
hx.add("Cr",     0.5)    # capacity rate ratio Cmin/Cmax
hx.add("C_min",  500.0, "W/K")
hx.add("T_h_in", 90.0,  "K")   # hot inlet (relative, used for Q calc)
hx.add("T_c_in", 20.0,  "K")   # cold inlet

@anvil.relation
def hx_effectiveness(NTU, Cr):
    eps = (1 - np.exp(-NTU * (1 - Cr))) / (1 - Cr * np.exp(-NTU * (1 - Cr)))
    return {"effectiveness": eps}

@anvil.relation
def hx_duty(effectiveness, C_min, T_h_in, T_c_in):
    Q_max = C_min * (T_h_in - T_c_in)
    return {"Q_duty": effectiveness * Q_max}

hx.use(hx_effectiveness)
hx.use(hx_duty)

# Maximize effectiveness by tuning NTU (proxy for heat exchanger size/cost)
opt_hx = hx.optimize(
    objective="effectiveness",
    design_vars={"NTU": (0.1, 10.0), "Cr": (0.1, 1.0)},
    minimize=False,
    method="L-BFGS-B",     # gradient-based: smooth landscape
    maxiter=200,
)

print(f"  Best effectiveness : {opt_hx.fun:.4f}  (max possible = 1.0)")
print(f"  Optimal NTU        : {opt_hx.x['NTU']:.3f}")
print(f"  Optimal Cr         : {opt_hx.x['Cr']:.3f}")
print(f"  Heat duty          : {float(opt_hx['Q_duty'].value):.0f} W")

# --------------------------------------------------------------
# Part 5: OptimizeResult API summary
# --------------------------------------------------------------
print("\n[5] OptimizeResult API")
print(f"  opt.x         = {dict(opt.x)}")
print(f"  opt.fun       = {opt.fun:.4g}")
print(f"  opt.success   = {opt.success}")
print(f"  opt.nfev      = {opt.nfev}  (system solves)")
print(f"  opt.nit       = {opt.nit}  (optimizer iterations)")
print(f"  opt.message   = {opt.message!r}")
print(f"  opt['Isp']    = {opt['Isp']}  (subscript -> Quantity at optimum)")
print(f"  'thrust' in opt = {'thrust' in opt}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
