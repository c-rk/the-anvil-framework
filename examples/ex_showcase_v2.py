#!/usr/bin/env python3
"""
Anvil Framework -- Complete Showcase
=====================================
Demonstrates every major feature in one runnable file.

  1.  Unit engine         -- Q(), arithmetic, conversions, UnitStub syntax
  2.  Define relations    -- @anvil.relation, Relation(), Relation.block()
  3.  One-shot solve      -- anvil.solve(func, **kwargs)
  4.  System API          -- system(), .add(kwargs), .use(), .solve()
  5.  Built-in RSQs       -- R.isentropic_ratios, R.normal_shock, S.rocket_nozzle
  6.  Coupled solve       -- Gauss-Seidel with monitor, convergence plot
  7.  Parametric sweep    -- .sweep(), .summary(), plot_sweep()
  8.  Sensitivity         -- .sensitivity().summary()
  9.  Dependency graph    -- plot_system()
  10. ODE solvers         -- explicit RK45, stiff BDF
  11. BVP solver          -- boundary value problem
  12. 1D heat PDE         -- Crank-Nicolson finite difference
  13. NASA CEA            -- detonation adapter, full output
  14. Registry operations -- push, update, search, list, export

All plots saved as PNG files (headless-safe).

Run:
    cd anvil-03-1
    python examples/ex_showcase_v2.py
"""

import os
import sys

import numpy as np

# --- path setup ----------------------------------------------------------

import anvil
from anvil import (
    BTU,
    MJ,
    Adapter,
    GPa,
    J,
    K,
    MPa,
    N,
    Pa,
    Q,
    Quantity,
    Relation,
    System,
    W,
    atm,
    bar,
    cm,
    ft,
    g_mol,
    kg,
    kg_mol,
    kJ,
    km,
    kN,
    kPa,
    kW,
    lb,
    lbf,
    m,
    mm,
    mol,
    monitor,
    ms,
    s,
    solvers,
    viz,
)

OUT_DIR = os.path.dirname(__file__)  # save PNGs next to this file


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


# =========================================================================
# 1. UNIT ENGINE
# =========================================================================
section("1. UNIT ENGINE")

# --- 1a. Classic Q() syntax ---
T_chamber = Q(3500, "K", name="T_chamber")
P_chamber = Q(6.9e6, "Pa", name="P_chamber")
mdot = Q(12.5, "kg/s", name="mdot")
area = Q(0.1, "m^2", name="area")

print(f"\nClassic Q():")
print(f"  T_chamber = {T_chamber}")
print(f"  P_chamber = {P_chamber}")
print(f"  mdot      = {mdot}")

# --- 1b. UnitStub syntax: value * unit ---
T_amb = 298.15 * K  # -> Q(298.15, "K")
P_atm = 101325 * Pa  # -> Q(101325, "Pa")
v_sound = 340.0 * (m / s)  # -> Q(340.0, "m/s")
g_earth = 9.80665 * m / s**2  # -> Q(9.80665, "m/s^2")  -- no parens needed
rho_air = 1.225 * kg / m**3  # -> Q(1.225, "kg/m^3")   -- no parens needed
cp_air = 1005.0 * J / kg / K  # -> Q(1005.0, "J/kg/K")
mu_air = 1.789e-5 * Pa * s  # -> Q(1.789e-5, "Pa*s")

print(f"\nUnitStub syntax:")
print(f"  T_amb    = {T_amb}")
print(f"  v_sound  = {v_sound}")
print(f"  g_earth  = {g_earth}")
print(f"  rho_air  = {rho_air}")
print(f"  cp_air   = {cp_air}")
print(f"  mu_air   = {mu_air}")

# Imperial units
V_jet = 550.0 * (ft / s)  # -> Q(550, "ft/s")  -- SI internally
F_drag = 150.0 * lbf  # -> Q(150 lbf in N)
L_wing = 12.5 * ft
print(f"\n  V_jet  = {V_jet}  ->  {V_jet.to("m/s")}")
print(f"  F_drag = {F_drag} ->  {F_drag.to("N")}")

# --- 1c. Quantity arithmetic ---
KE = 0.5 * rho_air * v_sound**2  # dynamic pressure
Re = rho_air * v_sound * (1.0 * m) / mu_air
print(f"\nArithmetic:")
print(f"  q_dyn = 12rhoV2 = {KE}")
print(f"  Re    = rhoVL/mu = {Re}")

# --- 1d. Unit conversion ---
T_K = Q(1000, "K")
T_R = T_K.to("R")  # Kelvin -> Rankine (same dimension, different scale)
P_Pa = Q(10e6, "Pa")
P_bar = P_Pa.to("bar")
P_psi = P_Pa.to("psi")
P_MPa = P_Pa.to("MPa")

print(f"\nUnit conversions:")
print(f"  {T_K}  ->  {T_R}")
print(f"  {P_Pa} ->  {P_bar}  =  {P_psi}  =  {P_MPa}")

# --- 1e. SI access ---
print(f"\n  cp_air.si    = {cp_air}  (always in SI: J/kg/K)")
print(f"  cp_air.value = {cp_air} {cp_air.unit}")


# =========================================================================
# 2. DEFINING RELATIONS
# =========================================================================
section("2. DEFINING RELATIONS")


# --- 2a. Decorator syntax -- auto-registers in the registry ---
@anvil.relation(domain="thermo", tags=["ideal_gas"])
def ideal_gas_density(P, R_gas, T):
    """Ideal gas: rho = P / (R * T)"""
    return {"rho": Q(P / (R_gas * T), "kg/m^3")}


@anvil.relation(domain="thermo", tags=["acoustics"])
def speed_of_sound_gas(gamma, R_gas, T):
    """Speed of sound in ideal gas: a = sqrt(gamma * R * T)"""
    return {"a_sound": Q((gamma * R_gas * T) ** 0.5, "m/s")}


@anvil.relation(domain="aero", tags=["reynolds"])
def reynolds_num(rho, V, L_char, mu):
    """Reynolds number: Re = rho V L / mu"""
    return {"Re": rho * V * L_char / mu}


print(f"\n@relation auto-registered: {ideal_gas_density}")
print(f"  inputs:  {ideal_gas_density.inputs}")
print(f"  outputs: {ideal_gas_density.outputs}")


# --- 2b. Relation() explicit wrap ---
def nusselt_dittus_boelter(Re, Pr, heating=True):
    """Dittus-Boelter: Nu = 0.023 * Re^0.8 * Pr^n"""
    n = 0.4 if heating else 0.3
    Nu = 0.023 * Re**0.8 * Pr**n
    return {"Nu": Nu}


nu_rel = Relation(nusselt_dittus_boelter, tags=["convection", "heat_transfer"])
print(f"\nRelation() wrap: {nu_rel}")


# --- 2c. Relation.block() -- chain multiple functions ---
def sutherland(T, T_ref=288.15, mu_ref=1.789e-5, S=110.4):
    mu = mu_ref * (T / T_ref) ** 1.5 * (T_ref + S) / (T + S)
    return {"mu": mu}


def prandtl_air(mu, cp, k_cond=0.0257):
    Pr = mu * cp / k_cond
    return {"Pr": Pr}


air_props = Relation.block(
    "air_transport_props",
    steps=[sutherland, prandtl_air],
    desc="Sutherland viscosity + Prandtl number for air",
)
print(f"\nRelation.block(): {air_props}")
print(f"  inputs:  {air_props.inputs}")
print(f"  outputs: {air_props.outputs}")


# =========================================================================
# 3. ONE-SHOT SOLVE
# =========================================================================
section("3. ONE-SHOT SOLVE -- anvil.solve()")

# No System object needed; inputs passed as keyword arguments
r = anvil.solve(ideal_gas_density, P=101325.0, R_gas=287.0, T=298.15)
print(f"\nOne-shot solve -- ideal gas density:")
r.summary()

r2 = anvil.solve(speed_of_sound_gas, gamma=1.4, R_gas=287.0, T=298.15)
print(f"Speed of sound: {r2['a_sound']}")

# Works with registry names too
r3 = anvil.solve("isentropic_ratios", M=2.0, gamma=1.4)
print(f"\nisentropic_ratios at M=2: T0/T={r3['T0_T']:.4f}  P0/P={r3['P0_P']:.4f}")


# =========================================================================
# 4. SYSTEM API
# =========================================================================
section("4. SYSTEM API -- system(), add(kwargs), use(), solve()")

# --- 4a. Build and solve a compressible nozzle flow system ---
nozzle = anvil.system("de_laval_nozzle")

# New kwargs-style add -- name inferred from keyword
nozzle.add(
    P0=8.0e6 * Pa,  # chamber total pressure
    T0=3300.0 * K,  # chamber total temperature
    gamma=Q(1.22),  # ratio of specific heats (dimensionless)
    R_gas=380.0 * J / kg / K,
    A_throat=0.001 * m**2,
    A_exit=Q(0.07, "m^2"),
    P_amb=P_atm,
)

# Can also mix old style
nozzle._add_single("P_amb", P_atm)  # (overwrite with same value, fine)

nozzle.use("nozzle_area_ratio")
nozzle.use("area_mach_supersonic")
nozzle.use("isentropic_ratios", map={"M": "M_exit"})
nozzle.use("exit_conditions")
nozzle.use("exit_velocity")
nozzle.use("choked_mass_flow")
nozzle.use("rocket_thrust")
nozzle.use("specific_impulse")

result = nozzle.solve(verbose=True)
result.summary()

# --- 4b. Result access ---
thrust = result["thrust"]
Isp = result["Isp"]
mdot_r = result["mdot"]
V_exit = result["V_exit"]

print(f"\nKey outputs:")
print(f"  Thrust = {thrust.to("kN")}")
print(f"  Isp    = {Isp}")
print(f"  mdot   = {mdot_r}")
print(f"  V_exit = {V_exit.to("km/s")}")

# --- 4c. Export results ---
result.to_csv(os.path.join(OUT_DIR, "nozzle_result.csv"))
print(f"\n  Saved: nozzle_result.csv")

json_str = result.to_json()
print(f"  JSON (first 150 chars): {json_str[:150]}...")


# =========================================================================
# 5. BUILT-IN RSQs
# =========================================================================
section("5. BUILT-IN RSQs (R and S namespaces)")

# --- 5a. Direct relation calls (no System needed) ---
print("\nIsentropic ratios at M=3, gamma=1.4:")
r_isen = anvil.R.isentropic_ratios(M=3.0, gamma=1.4)
print(f"  T0/T   = {r_isen['T0_T']:.4f}")
print(f"  P0/P   = {r_isen['P0_P']:.4f}")
print(f"  rho0/rho   = {r_isen['rho0_rho']:.4f}")

print("\nNormal shock at M1=2.5:")
r_shock = anvil.R.normal_shock(M1=2.5, gamma=1.4)
print(f"  M2     = {r_shock['M2']:.4f}")
print(f"  P2/P1  = {r_shock['P2_P1']:.4f}")
print(f"  T2/T1  = {r_shock['T2_T1']:.4f}")
print(f"  P02/P01= {r_shock['P02_P01']:.5f}  (stagnation pressure loss)")

print("\nHohmann transfer: LEO (400 km) -> GEO (35 786 km):")
R_earth = 6.371e6  # m
mu_earth = 3.986e14  # m^3/s^2
r1 = R_earth + 400e3
r2 = R_earth + 35786e3
r_hohmann = anvil.R.hohmann_transfer(mu=mu_earth, r1=r1, r2=r2)
print(f"  DV1    = {r_hohmann['dv1'].to("km/s")}")
print(f"  DV2    = {r_hohmann['dv2'].to("km/s")}")
print(f"  DV_tot = {r_hohmann['dv_total'].to("km/s")}")
print(f"  TOF    = {Q(float(r_hohmann['tof']._si_value) / 3600, 'hr')}")

# --- 5b. Pre-built rocket nozzle System ---
print("\nPre-built rocket_nozzle System:")
rn = anvil.S.rocket_nozzle.copy()
rn.set(P0=10e6, T0=3600, gamma=1.2, R_gas=400.0, A_throat=0.015, A_exit=0.12)
rn.solve().summary()


# =========================================================================
# 6. COUPLED SOLVE -- GAUSS-SEIDEL + MONITOR
# =========================================================================
section("6. COUPLED SOLVE -- Gauss-Seidel + Convergence History")

# Coupled fixed-point system (Gauss-Seidel converges by design):
#   y1 = sqrt(y2 + 4.0)     (y1 depends on y2)
#   y2 = sqrt(y1)            (y2 depends on y1)
#
# Solution satisfies y1 = sqrt(sqrt(y1) + 4)
# Numerically: y1 ~ 2.4353, y2 ~ 1.5606


@anvil.relation(domain="math", register=False)
def fp_eq1(y2):
    return {"y1": (y2 + 4.0) ** 0.5}


@anvil.relation(domain="math", register=False)
def fp_eq2(y1):
    return {"y2": y1**0.5}


coupled_sys = anvil.system("fixed_point_demo")
coupled_sys.add("y2", 1.0)  # initial guess for y2
coupled_sys.use(fp_eq1)
coupled_sys.use(fp_eq2)

result_coupled = coupled_sys.solve(
    method="gauss_seidel",
    max_iter=200,
    rtol=1e-8,
    monitor=True,
    verbose=True,
)
result_coupled.summary()

# Verify fixed-point consistency
y1_val = float(result_coupled["y1"]._si_value)
y2_val = float(result_coupled["y2"]._si_value)
print(f"\n  Check: y1 == sqrt(y2+4): {y1_val:.6f} vs {(y2_val + 4) ** 0.5:.6f}")
print(f"  Check: y2 == sqrt(y1):   {y2_val:.6f} vs {y1_val**0.5:.6f}")

# Convergence history plot
monitor.plot_convergence(
    coupled_sys, save=os.path.join(OUT_DIR, "convergence.png"), show=False
)
print(f"\n  Saved: convergence.png")

monitor.plot_variables(
    coupled_sys,
    variables=["y1", "y2"],
    save=os.path.join(OUT_DIR, "variable_trace.png"),
    show=False,
)
print(f"  Saved: variable_trace.png")


# =========================================================================
# 7. PARAMETRIC SWEEP
# =========================================================================
section("7. PARAMETRIC SWEEP")

sweep_nozzle = anvil.S.rocket_nozzle.copy()

# Sweep chamber pressure from 2 MPa to 12 MPa
P0_values = np.linspace(2e6, 12e6, 12)  # Pa
sweep = sweep_nozzle.sweep("P0", P0_values, skip_errors=True)
sweep.summary(outputs=["thrust", "Isp", "mdot", "V_exit"])

# Export sweep data
sweep.to_csv(os.path.join(OUT_DIR, "sweep_pressure.csv"))
print(f"\n  Saved: sweep_pressure.csv")

# Plot sweep
monitor.plot_sweep(
    sweep,
    y=["thrust", "Isp", "mdot", "V_exit"],
    save=os.path.join(OUT_DIR, "sweep_plot.png"),
    show=False,
)
print(f"  Saved: sweep_plot.png")

# Sweep over area ratio (exit/throat)
sweep_nozzle2 = anvil.S.rocket_nozzle.copy()
A_exit_values = np.linspace(0.02, 0.16, 10)  # m^2
sweep2 = sweep_nozzle2.sweep("A_exit", A_exit_values, skip_errors=True)
sweep2.summary(outputs=["M_exit", "thrust", "Isp"])


# =========================================================================
# 8. SENSITIVITY ANALYSIS
# =========================================================================
section("8. SENSITIVITY ANALYSIS")

sens_sys = anvil.S.rocket_nozzle.copy()
sens = sens_sys.sensitivity(
    outputs=["thrust", "Isp", "mdot"],
    step=0.01,
)
sens.summary()

print(f"\nTop 3 drivers of Isp:")
for inp, val in sens.top("Isp", n=3):
    print(f"  {inp:20s}  {val:+.4f}")


# =========================================================================
# 9. DEPENDENCY GRAPH
# =========================================================================
section("9. DEPENDENCY GRAPH")

dep_sys = anvil.S.rocket_nozzle.copy()
try:
    dep_sys.validate()
except Exception:
    pass

monitor.plot_system(
    dep_sys, save=os.path.join(OUT_DIR, "dependency_graph.png"), show=False
)
print(f"  Saved: dependency_graph.png")


# =========================================================================
# 10. ODE SOLVERS
# =========================================================================
section("10. ODE SOLVERS")

# --- 10a. Explicit RK45: radioactive decay chain ---
print("\n--- Explicit RK45: two-species decay  A -> B -> products ---")
# dA/dt = -k1 * A
# dB/dt = +k1 * A - k2 * B
k1, k2 = 0.1, 0.3  # 1/s


def decay_chain(t, y):
    A, B = y
    return [-k1 * A, k1 * A - k2 * B]


t_span = (0.0, 30.0)
y0 = [1.0, 0.0]
t_eval = np.linspace(0, 30, 300)

sol = solvers.solve_ode(decay_chain, t_span, y0, t_eval=t_eval, rtol=1e-8, verbose=True)
A_final = sol["y"][0, -1]
B_max = sol["y"][1].max()
t_Bmax = t_eval[np.argmax(sol["y"][1])]
print(f"  A(30 s)  = {A_final:.6f}  (exact: {np.exp(-k1 * 30):.6f})")
print(f"  B_max    = {B_max:.4f}  at t ~ {t_Bmax:.2f} s")
print(f"  nfev     = {sol['nfev']}")

# Plot ODE result
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(sol["t"], sol["y"][0], label="A(t)", color="steelblue")
    ax.plot(sol["t"], sol["y"][1], label="B(t)", color="tomato")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Concentration")
    ax.set_title("Decay chain A -> B -> products  (RK45)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "ode_decay_chain.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: ode_decay_chain.png")
except Exception as e:
    print(f"  Plot skipped: {e}")

# --- 10b. Stiff ODE: Robertson chemical kinetics ---
print("\n--- Stiff BDF: Robertson kinetics (classic benchmark) ---")


def robertson(t, y):
    k1, k2, k3 = 0.04, 3e7, 1e4
    return [
        -k1 * y[0] + k2 * y[1] * y[2],
        k1 * y[0] - k2 * y[1] * y[2] - k3 * y[1] ** 2,
        k3 * y[1] ** 2,
    ]


sol_stiff = solvers.solve_ode_stiff(
    robertson, (0, 1e11), [1.0, 0.0, 0.0], method="BDF", rtol=1e-8, verbose=True
)
y_end = sol_stiff["y"][:, -1]
print(f"  y(t=1e11): A={y_end[0]:.6f}  B={y_end[1]:.2e}  C={y_end[2]:.6f}")
print(f"  A + B + C = {y_end.sum():.8f}  (should = 1.0, conservation check)")

# --- 10c. ODE with event: find when B peaks ---
print("\n--- ODE with event: stop when dB/dt = 0 ---")


def dB_dt_zero(t, y):
    """Event: B reaches its maximum (dB/dt = 0)"""
    k1, k2 = 0.1, 0.3
    A, B = y
    return k1 * A - k2 * B  # zero when B peaks


dB_dt_zero.terminal = True
dB_dt_zero.direction = -1  # peak: going from + to -

sol_event = solvers.solve_ode(
    decay_chain, (0, 30), [1.0, 0.0], events=dB_dt_zero, rtol=1e-10
)
if sol_event["sol"].t_events[0].size > 0:
    t_peak = sol_event["sol"].t_events[0][0]
    y_peak = sol_event["sol"].y_events[0][0]
    print(
        f"  B peaks at t = {t_peak:.4f} s  (analytic: {np.log(k2 / k1) / (k2 - k1):.4f} s)"
    )
    print(f"  B_max = {y_peak[1]:.6f}")


# =========================================================================
# 11. BVP SOLVER
# =========================================================================
section("11. BOUNDARY VALUE PROBLEM (BVP)")

# Solve the heat conduction BVP:
#   -k T'' = q_dot  (volumetric heat source)
#   T(0) = T_left   (Dirichlet)
#   T(L) = T_right  (Dirichlet)
#
# Transform to first-order: y = [T, T']
#   y[0]' = y[1]
#   y[1]' = -q_dot / k

T_left_val = 300.0  # K
T_right_val = 500.0  # K
k_cond = 50.0  # W/m/K  (steel-ish)
q_dot = 1e6  # W/m^3  (volumetric heat source)
L_slab = 0.1  # m


def heat_bvp_rhs(x, y):
    """dy/dx = [T', T''] -> [y[1], -q_dot/k]"""
    return np.vstack([y[1], np.full_like(x, -q_dot / k_cond)])


def heat_bvp_bc(ya, yb):
    """Boundary: T(0) = T_left, T(L) = T_right"""
    return np.array([ya[0] - T_left_val, yb[0] - T_right_val])


# Initial mesh and guess (linear profile as starting guess)
x_mesh = np.linspace(0, L_slab, 10)
T_guess = np.linspace(T_left_val, T_right_val, 10)
y_guess = np.zeros((2, 10))
y_guess[0] = T_guess
y_guess[1] = (T_right_val - T_left_val) / L_slab  # constant slope guess

bvp_result = solvers.solve_bvp(heat_bvp_rhs, heat_bvp_bc, x_mesh, y_guess, verbose=True)

# Evaluate on fine grid
x_fine = np.linspace(0, L_slab, 200)
T_fine = bvp_result["sol"](x_fine)[0]

# Analytic solution: T(x) = T_left + (T_right-T_left)*x/L - q_dot/(2k) * x*(L-x)
T_analytic = (
    T_left_val
    + (T_right_val - T_left_val) * x_fine / L_slab
    - q_dot / (2 * k_cond) * x_fine * (L_slab - x_fine)
)

max_err = np.max(np.abs(T_fine - T_analytic))
T_max_numerical = T_fine.max()
T_max_analytic = T_analytic.max()

print(f"\n  T_max numerical = {T_max_numerical:.4f} K")
print(f"  T_max analytic  = {T_max_analytic:.4f} K")
print(f"  Max error       = {max_err:.4e} K  (BVP success={bvp_result['success']})")

try:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_fine * 100, T_fine, "-", label="BVP numerical", linewidth=2)
    ax.plot(x_fine * 100, T_analytic, "--", label="Analytic", linewidth=1.5)
    ax.set_xlabel("x [cm]")
    ax.set_ylabel("Temperature [K]")
    ax.set_title("Heat conduction with volumetric source -- BVP solution")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "bvp_heat.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: bvp_heat.png")
except Exception as e:
    print(f"  Plot skipped: {e}")


# =========================================================================
# 12. 1D HEAT PDE -- CRANK-NICOLSON
# =========================================================================
section("12. 1D HEAT EQUATION -- Crank-Nicolson FD")

# Fin cooling: Gaussian initial temperature distribution decays to walls
# alpha = k / (rho cp)  for aluminium
rho_al = 2700.0  # kg/m^3
cp_al = 900.0  # J/kg/K
k_al = 205.0  # W/m/K
alpha = k_al / (rho_al * cp_al)  # ~ 8.46e-5 m^2/s

print(f"\n  Aluminium alpha = {alpha:.4e} m2/s")

pde_result = solvers.solve_pde_heat_1d(
    alpha=alpha,
    x_span=(0.0, 0.1),  # 10 cm slab
    t_span=(0.0, 60.0),  # 60 second transient
    u_init=lambda x: 300.0 + 200.0 * np.exp(-500 * (x - 0.05) ** 2),
    bc_left=300.0,  # constant 300 K wall
    bc_right=300.0,  # constant 300 K wall
    nx=60,
    nt=600,  # 600 steps (Crank-Nicolson is unconditionally stable)
    verbose=True,
)

x = pde_result["x"]
t = pde_result["t"]
u = pde_result["u"]

T_center_init = u[0, 40]  # near x = 0.05 m
T_center_final = u[-1, 40]  # after 60 s
print(f"\n  T(center, t=0)  = {T_center_init:.2f} K")
print(f"  T(center, t=60) = {T_center_final:.2f} K  (cooled toward 300 K)")
print(
    f"  Grid: {pde_result['dx'] * 100:.2f} cm spacing, {pde_result['dt']:.3f} s time step"
)

try:
    import matplotlib.pyplot as plt
    from matplotlib import cm as mpl_cm

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Spatial profiles at several time snapshots
    ax1 = axes[0]
    t_indices = [0, len(t) // 6, len(t) // 3, len(t) // 2, len(t) - 1]
    colors = plt.cm.viridis(np.linspace(0, 1, len(t_indices)))
    for idx, col in zip(t_indices, colors):
        ax1.plot(x * 100, u[idx], color=col, label=f"t={t[idx]:.1f} s", linewidth=1.5)
    ax1.set_xlabel("x [cm]")
    ax1.set_ylabel("Temperature [K]")
    ax1.set_title("Temperature profiles at snapshots")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Center temperature vs time
    ax2 = axes[1]
    ax2.plot(t, u[:, 40], color="steelblue", linewidth=2)
    ax2.axhline(300, color="gray", linestyle="--", label="Wall T = 300 K")
    ax2.set_xlabel("Time [s]")
    ax2.set_ylabel("Temperature [K]")
    ax2.set_title("Center temperature vs time")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.suptitle(
        "1D Heat Equation -- Crank-Nicolson (aluminium slab)",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "pde_heat_1d.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: pde_heat_1d.png")
except Exception as e:
    print(f"  Plot skipped: {e}")


# =========================================================================
# 13. NASA CEA DETONATION ADAPTER
# =========================================================================
section("13. NASA CEA -- Chapman-Jouguet Detonation")

from anvil.adapters.nasa_cea_detonation import cea_detonation

# Single call -- full output
print("\n--- H2/O2 stoichiometric at 1 atm, 300 K ---")
cea_r = cea_detonation.func(
    fuel="H2",
    oxidizer="O2",
    fuel_moles=2.0,
    ox_moles=1.0,
    T1=300.0,
    P1=101325.0,
)

print("\n  Core CJ state:")
core_keys = ["D_CJ", "T_CJ", "P_CJ", "P_ratio", "rho_CJ", "gamma_CJ", "a_CJ", "u_CJ"]
for k in core_keys:
    v = cea_r[k]
    if isinstance(v, Q):
        print(f"    {k:10s} = {v} {v.unit}")
    else:
        print(f"    {k:10s} = {v:.4f}")

print("\n  Thermochemical:")
for k in ["cp_CJ", "cv_CJ", "e_CJ", "h_CJ"]:
    v = cea_r[k]
    print(f"    {k:10s} = {v} {v.unit}")

print("\n  Transport:")
for k in ["mu_CJ", "k_CJ", "Pr_CJ"]:
    v = cea_r[k]
    if isinstance(v, Q):
        print(f"    {k:10s} = {v} {v.unit}")
    else:
        print(f"    {k:10s} = {v:.4f}")

print("\n  Product species (mole fractions):")
sp = cea_r.get("species_CJ", {})
if sp:
    for name, frac in sorted(sp.items(), key=lambda x: -x[1]):
        bar_str = "#" * int(frac * 30)
        print(f"    {name:8s}  {frac:.4f}  {bar_str}")
else:
    print("    (species not available in this CEA version)")

# Verify adapter info
print(f"\n{cea_detonation.info()}")

# Sweep over initial pressure: 0.5 -> 5 atm
print("\n--- Pressure sweep: 0.5 -> 5 atm ---")
P1_vals_Pa = np.linspace(0.5 * 101325, 5 * 101325, 8)
D_vals, T_vals, P_ratio_vals = [], [], []

for P1 in P1_vals_Pa:
    r_p = cea_detonation.func(
        fuel="H2", oxidizer="O2", fuel_moles=2.0, ox_moles=1.0, T1=300.0, P1=float(P1)
    )
    D_vals.append(float(r_p["D_CJ"]._si_value))
    T_vals.append(float(r_p["T_CJ"]._si_value))
    P_ratio_vals.append(r_p["P_ratio"])

print(f"\n  {'P1 [atm]':>10}  {'D_CJ [m/s]':>12}  {'T_CJ [K]':>10}  {'P_ratio':>8}")
print(f"  {'-' * 46}")
for P1, D, T, PR in zip(P1_vals_Pa, D_vals, T_vals, P_ratio_vals):
    print(f"  {P1 / 101325:>10.2f}  {D:>12.1f}  {T:>10.1f}  {PR:>8.2f}")

# Plot CEA pressure sweep
try:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    P_atm_arr = P1_vals_Pa / 101325
    labels_data = [
        ("D_CJ [m/s]", D_vals),
        ("T_CJ [K]", T_vals),
        ("P2/P1", P_ratio_vals),
    ]
    for ax, (ylabel, ydata) in zip(axes, labels_data):
        ax.plot(P_atm_arr, ydata, "o-", color="firebrick", linewidth=1.5, markersize=5)
        ax.set_xlabel("P1 [atm]")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    fig.suptitle(
        "H2/O2 CJ Detonation -- Pressure Sweep", fontsize=12, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "cea_pressure_sweep.png"), dpi=150)
    plt.close(fig)
    print(f"\n  Saved: cea_pressure_sweep.png")
except Exception as e:
    print(f"  Plot skipped: {e}")

# Fuel comparison at 1 atm
print("\n--- Fuel comparison at 1 atm, T1=300 K ---")
fuels = [
    ("H2", "O2", 2.0, 1.0),
    ("CH4", "O2", 1.0, 2.0),
    ("C2H4", "O2", 1.0, 3.0),
    ("C3H8", "O2", 1.0, 5.0),
]
print(
    f"  {'Fuel':>6}  {'D_CJ [m/s]':>12}  {'T_CJ [K]':>10}  {'P_ratio':>8}  "
    f"{'gamma_CJ':>6}  {'a_CJ [m/s]':>12}"
)
print(f"  {'-' * 62}")
for fuel_name, ox_name, fm, om in fuels:
    rc = cea_detonation.func(
        fuel=fuel_name,
        oxidizer=ox_name,
        fuel_moles=fm,
        ox_moles=om,
        T1=300.0,
        P1=101325.0,
    )
    print(
        f"  {fuel_name:>6}  "
        f"{float(rc['D_CJ']._si_value):>12.1f}  "
        f"{float(rc['T_CJ']._si_value):>10.1f}  "
        f"{rc['P_ratio']:>8.2f}  "
        f"{rc['gamma_CJ']:>6.3f}  "
        f"{float(rc['a_CJ']._si_value):>12.1f}"
    )


# =========================================================================
# 14. REGISTRY OPERATIONS
# =========================================================================
section("14. REGISTRY OPERATIONS")


# --- 14a. Register a custom relation ---
@anvil.relation(domain="heat_transfer.fins", tags=["fin", "efficiency"])
def fin_effectiveness(h, P_fin, k_fin, A_c, A_total):
    """
    Fin effectiveness: ratio of heat transfer with fin to without fin.
    eps = Q_fin / Q_without_fin
    """
    import numpy as np

    m = (h * P_fin / (k_fin * A_c)) ** 0.5
    L = A_c / P_fin  # characteristic length
    Q_fin = (h * P_fin * k_fin * A_c) ** 0.5  # per unit DT
    Q_no_fin = h * A_c
    effectiveness = Q_fin / Q_no_fin
    return {"fin_eff": effectiveness}


print(f"\nRegistered: fin_effectiveness")
print(fin_effectiveness.info())  # use the object directly (namespace rebuild is async)

# --- 14b. Search registry ---
print("\nSearch 'compressible':")
hits = anvil.registry.search("compressible")
for h in hits[:4]:
    print(f"  [{h['type']}] {h['name']:30s}  {h['description'][:50]}")

print("\nSearch 'orbital':")
hits2 = anvil.registry.search("orbital")
for h in hits2:
    print(f"  [{h['type']}] {h['name']:30s}  {h['description'][:50]}")

# --- 14c. List by domain ---
print("\nList domain='aero':")
anvil.registry.list(domain="aero")

# --- 14d. Detailed info on a specific RSQ ---
print("\nInfo on 'normal_shock':")
anvil.registry.info("normal_shock")


# --- 14e. Update an existing RSQ ---
@anvil.relation(
    domain="heat_transfer.fins",
    tags=["fin", "efficiency", "v2"],
    name="fin_effectiveness",
    register=False,
)
def fin_effectiveness_v2(h, P_fin, k_fin, A_c, A_total):
    """Fin effectiveness -- improved (includes fin tip correction)."""
    m_val = (h * P_fin / (k_fin * A_c)) ** 0.5
    L_c = A_c / P_fin + A_c / P_fin * 0.05  # tip correction ~ 5%
    mL = m_val * L_c
    import numpy as np

    Q_fin = (h * P_fin * k_fin * A_c) ** 0.5 * np.tanh(mL) / mL
    Q_no_fin = h * A_c
    return {"fin_eff": Q_fin / Q_no_fin}


anvil.update(
    fin_effectiveness_v2,
    name="fin_effectiveness",
    domain="heat_transfer.fins",
    tags=["fin", "efficiency", "v2"],
)

# --- 14f. Export source ---
print("\nExport source of 'ideal_gas_density':")
anvil.registry.export("ideal_gas_density")


# =========================================================================
# FINAL SUMMARY
# =========================================================================
section("FILES SAVED")
saved = [
    "nozzle_result.csv",
    "sweep_pressure.csv",
    "convergence.png",
    "variable_trace.png",
    "sweep_plot.png",
    "dependency_graph.png",
    "ode_decay_chain.png",
    "bvp_heat.png",
    "pde_heat_1d.png",
    "cea_pressure_sweep.png",
]
for f in saved:
    path = os.path.join(OUT_DIR, f)
    exists = os.path.exists(path)
    print(f"  {'OK' if exists else 'MISSING':6s}  {f}")

print(f"\n{'=' * 65}")
print(f"  Anvil Framework showcase complete.")
print(f"{'=' * 65}\n")
