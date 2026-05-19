"""
Example 11: ODE, BVP, and PDE Solvers
======================================

Demonstrates:
    - solve_ode()       — non-stiff ODE (RK45): satellite reentry drag
    - solve_ode_stiff() — stiff ODE (BDF): chemical kinetics
    - solve_bvp()       — boundary value problem: fin temperature profile
    - solve_pde_heat_1d() — 1D heat equation: transient wall heating
    - Plotting results with anvil.viz (if matplotlib available)

Engineering context:
    Four self-contained problems that cover the full range of differential
    equation solvers in anvil.solvers.
"""

import sys, os
import numpy as np


import anvil
from anvil import Q
from anvil import solvers

print("=" * 60)
print("  Example 11: ODE / BVP / PDE Solvers")
print("=" * 60)


# =====================================================
# Part A: Non-stiff ODE — satellite reentry drag
#
# State: [v, h]   v = speed (m/s), h = altitude (m)
# dv/dt = -D/m - g*sin(gamma)     (deceleration)
# dh/dt = -v * sin(gamma)          (altitude loss)
#
# Simplified: constant flight-path angle gamma = 3 deg,
# exponential atmosphere, drag-only deceleration.
# =====================================================
print("\n" + "=" * 40)
print("  Part A: Satellite Reentry (RK45)")
print("=" * 40)

rho0    = 1.225       # kg/m^3 — sea-level density
H_scale = 8500.0      # m      — scale height
Cd      = 1.2         # drag coefficient (blunt capsule)
A       = 10.0        # m^2    — cross-section area
m       = 1500.0      # kg     — capsule mass
g       = 9.80665     # m/s^2
gamma   = np.radians(3.0)  # flight-path angle (shallow entry)

def reentry(t, y):
    v, h = y
    h = max(h, 0.0)
    rho = rho0 * np.exp(-h / H_scale)
    D = 0.5 * rho * Cd * A * v**2
    dvdt = -(D / m) - g * np.sin(gamma)
    dhdt = -v * np.sin(gamma)
    return [dvdt, dhdt]

v0 = 7800.0   # m/s — orbital entry speed
h0 = 120e3    # m   — entry altitude 120 km

t_eval = np.linspace(0, 500, 2000)
sol_a = solvers.solve_ode(
    reentry,
    t_span=(0, 500),
    y0=[v0, h0],
    method="RK45",
    t_eval=t_eval,
    rtol=1e-8,
    atol=1e-10,
    verbose=True,
)

v_final = sol_a["y"][0, -1]
h_final = sol_a["y"][1, -1]
t_ground_idx = np.argmin(np.abs(sol_a["y"][1]))  # closest to h=0

print(f"\n  Entry conditions:")
print(f"    v0 = {v0:.0f} m/s,  h0 = {h0/1e3:.0f} km")
print(f"  After {sol_a['t'][-1]:.0f} s:")
print(f"    v  = {v_final:.0f} m/s,  h = {h_final/1e3:.1f} km")
print(f"  Peak deceleration at t ≈ {sol_a['t'][np.gradient(sol_a['y'][0]).argmin()]:.0f} s")
print(f"  ODE solved in {sol_a['nfev']} function evaluations")


# =====================================================
# Part B: Stiff ODE — chemical kinetics (A → B → C)
#
# Classic stiff problem: two reactions with very
# different time constants (τ1 << τ2).
#
# d[A]/dt = -k1 * [A]
# d[B]/dt =  k1 * [A]  -  k2 * [B]
# d[C]/dt =  k2 * [B]
#
# k1 = 1000 s^-1 (fast),  k2 = 0.01 s^-1 (slow)
# =====================================================
print("\n" + "=" * 40)
print("  Part B: Chemical Kinetics A→B→C (BDF)")
print("=" * 40)

k1 = 1000.0   # fast reaction
k2 = 0.01     # slow reaction

def kinetics(t, y):
    A, B, C = y
    dA = -k1 * A
    dB =  k1 * A - k2 * B
    dC =  k2 * B
    return [dA, dB, dC]

t_end = 300.0   # s — watch the slow reaction complete

sol_b = solvers.solve_ode_stiff(
    kinetics,
    t_span=(0, t_end),
    y0=[1.0, 0.0, 0.0],    # all species A initially
    method="BDF",
    t_eval=np.linspace(0, t_end, 500),
    rtol=1e-6,
    atol=1e-10,
    verbose=True,
)

A_f, B_f, C_f = sol_b["y"][:, -1]
print(f"\n  Rate constants: k1 = {k1} s⁻¹ (fast),  k2 = {k2} s⁻¹ (slow)")
print(f"  At t = {t_end:.0f} s:")
print(f"    [A] = {A_f:.6f}   (consumed by fast reaction)")
print(f"    [B] = {B_f:.6f}   (intermediate)")
print(f"    [C] = {C_f:.6f}   (product of slow reaction)")
print(f"    Sum = {A_f+B_f+C_f:.8f}  (should be 1.0 — mass conservation)")
print(f"  Solved in {sol_b['nfev']} rhs evaluations")

# Compare: would RK45 fail on this stiff system?
print(f"\n  Note: RK45 step-size constraint ≈ 1/k1 = {1/k1:.1e} s")
print(f"  BDF adapts automatically — no user tuning needed.")


# =====================================================
# Part C: Boundary Value Problem — fin temperature
#
# Extended surface (fin) with tip insulated:
#   d²T/dx² - m² * (T - T_inf) = 0
#
#   BC: T(0) = T_base  (fin base temperature)
#       dT/dx|_{x=L} = 0  (insulated tip)
#
# Solution: T(x) = T_inf + (T_base - T_inf) * cosh(m*(L-x)) / cosh(m*L)
# =====================================================
print("\n" + "=" * 40)
print("  Part C: Fin Temperature (BVP)")
print("=" * 40)

T_base = 400.0    # K — fin base
T_inf  = 300.0    # K — ambient
h_conv = 50.0     # W/m^2/K — convection coefficient
k_fin  = 200.0    # W/m/K — aluminum
t_fin  = 0.002    # m — fin thickness
L_fin  = 0.1      # m — fin length (10 cm)

P_perim = 2 * (t_fin + 0.05)   # m — perimeter (assume 5 cm width)
A_cs    = t_fin * 0.05          # m^2 — cross section
m_fin   = np.sqrt(h_conv * P_perim / (k_fin * A_cs))

print(f"\n  Fin: L={L_fin*100:.0f} cm,  t={t_fin*1000:.0f} mm,  k={k_fin} W/m/K")
print(f"  h_conv = {h_conv} W/m²/K,  m = {m_fin:.2f} m⁻¹")

def fin_ode(x, y):
    # y[0] = T - T_inf,  y[1] = dT/dx
    return np.vstack([y[1], m_fin**2 * y[0]])

def fin_bc(ya, yb):
    # ya[0] = T_base - T_inf (at x=0)
    # yb[1] = 0             (insulated tip)
    return np.array([ya[0] - (T_base - T_inf), yb[1]])

x_init = np.linspace(0, L_fin, 8)
theta0 = (T_base - T_inf) * np.cosh(m_fin * (L_fin - x_init)) / np.cosh(m_fin * L_fin)
y_init = np.zeros((2, x_init.size))
y_init[0] = theta0
y_init[1] = -m_fin * (T_base - T_inf) * np.sinh(m_fin * (L_fin - x_init)) / np.cosh(m_fin * L_fin)

sol_c = solvers.solve_bvp(
    fin_ode,
    fin_bc,
    x=x_init,
    y_init=y_init,
    tol=1e-6,
    verbose=False,
)

x_fine = np.linspace(0, L_fin, 50)
T_numerical = T_inf + sol_c["sol"](x_fine)[0]
T_analytical = T_inf + (T_base - T_inf) * np.cosh(m_fin * (L_fin - x_fine)) / np.cosh(m_fin * L_fin)
max_err = np.max(np.abs(T_numerical - T_analytical))

T_tip_num = T_inf + sol_c["y"][0, -1]
T_tip_ana = T_inf + (T_base - T_inf) / np.cosh(m_fin * L_fin)

print(f"\n  Tip temperature (numerical):  {T_tip_num:.3f} K")
print(f"  Tip temperature (analytical): {T_tip_ana:.3f} K")
print(f"  Max error vs analytical:      {max_err:.2e} K")

# Fin efficiency
Q_actual  = k_fin * A_cs * m_fin * (T_base - T_inf) * np.tanh(m_fin * L_fin)
Q_max     = h_conv * P_perim * L_fin * (T_base - T_inf)
eta_fin   = Q_actual / Q_max
print(f"\n  Heat removed: {Q_actual:.1f} W")
print(f"  Fin efficiency: {eta_fin:.3f}  ({eta_fin*100:.1f}%)")


# =====================================================
# Part D: 1D Heat Equation (PDE) — wall thermal soak
#
# Steel wall initially at T_amb. One face suddenly
# exposed to high-temperature gas (step input).
# Track temperature history through the wall.
#
# ∂T/∂t = α ∂²T/∂x²
# BC: T(0,t) = T_gas (hot face)
#     T(L,t) = T_amb (cold face, heat sink)
# IC: T(x,0) = T_amb
# =====================================================
print("\n" + "=" * 40)
print("  Part D: Wall Thermal Soak (1D PDE)")
print("=" * 40)

T_gas   = 1200.0    # K — gas temperature (step input)
T_amb   = 300.0     # K — initial wall / cold-face temperature
L_wall  = 0.025     # m — 25 mm steel wall
alpha   = 1.2e-5    # m^2/s — thermal diffusivity of steel
rho_cp  = 3.9e6     # J/m^3/K — volumetric heat capacity (for Q calc)

print(f"\n  Wall: L={L_wall*1000:.0f} mm,  α={alpha:.2e} m²/s")
print(f"  Step from T_amb={T_amb} K to T_gas={T_gas} K on hot face")
print(f"  Fourier number at t=60s: Fo = α·t/L² = {alpha*60/L_wall**2:.2f}")

sol_d = solvers.solve_pde_heat_1d(
    alpha=alpha,
    x_span=(0, L_wall),
    t_span=(0, 120),
    u_init=lambda x: np.full_like(x, T_amb),
    bc_left=T_gas,
    bc_right=T_amb,
    nx=80,
    verbose=True,
)

x_wall = sol_d["x"]
t_pde  = sol_d["t"]
T_pde  = sol_d["u"]

# Print temperature profile at several time snapshots
print(f"\n  Temperature profile through wall at key times (K):")
print(f"  {'x(mm)':>6s}", end="")
for t_snap in [5, 15, 30, 60, 120]:
    print(f"  {t_snap:>6.0f}s", end="")
print()

for xi in [0.0, 0.005, 0.010, 0.015, 0.020, 0.025]:
    ix = np.argmin(np.abs(x_wall - xi))
    print(f"  {xi*1000:>6.1f}", end="")
    for t_snap in [5, 15, 30, 60, 120]:
        it = np.argmin(np.abs(t_pde - t_snap))
        print(f"  {T_pde[it, ix]:>6.0f}", end="")
    print()

# Time to reach 500 K at mid-wall
ix_mid = len(x_wall) // 2
T_mid  = T_pde[:, ix_mid]
i_500  = np.argmax(T_mid >= 500.0)
if i_500 > 0:
    print(f"\n  Time for mid-wall to reach 500 K: {t_pde[i_500]:.1f} s")

# Heat flux at hot face (Fourier's law, approximate)
dTdx_hot = (T_pde[-1, 1] - T_pde[-1, 0]) / sol_d["dx"]
k_steel   = alpha * rho_cp
q_flux    = -k_steel * dTdx_hot
print(f"  Heat flux at hot face (t=120s): {q_flux/1000:.1f} kW/m²")


# =====================================================
# Part E: Use the dense ODE output (callable solution)
# =====================================================
print("\n" + "=" * 40)
print("  Part E: Dense ODE Output")
print("=" * 40)

# The sol object from solve_ode is callable: sol(t) → y(t)
dense_sol = sol_b["sol"]   # from the kinetics problem
t_query = np.array([0.001, 0.01, 0.1, 1.0, 10.0, 100.0])
y_query = dense_sol.sol(t_query)

print(f"\n  Kinetics concentrations at arbitrary t (dense output):")
print(f"  {'t(s)':>10s}  {'[A]':>12s}  {'[B]':>12s}  {'[C]':>12s}")
for i, t in enumerate(t_query):
    print(f"  {t:>10.3f}  {y_query[0, i]:>12.6f}  {y_query[1, i]:>12.6f}  {y_query[2, i]:>12.6f}")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
