"""
Example 13: Control Systems Analysis
======================================

Demonstrates:
    - pid_output RSQ          — PID controller output from error signals
    - ziegler_nichols_pid RSQ — auto-tune PID gains from ultimate gain/period
    - second_order_metrics RSQ — step response characteristics (OS%, t_settle)
    - routh_hurwitz_2nd RSQ   — closed-loop stability check
    - solve_ode()             — simulate the closed-loop step response
    - solve_forward()         — DAG system for design calculations
    - sweep()                 — bandwidth vs damping ratio trade study

Engineering context:
    Design a flight control law for an attitude hold loop. The plant is
    a second-order system (rigid body + actuator lag). Use Ziegler-Nichols
    to get initial PID gains, then sweep damping ratio to balance speed
    and overshoot.
"""

import sys, os
import numpy as np


import anvil
from anvil import Q, System
from anvil import solvers

print("=" * 60)
print("  Example 13: Control Systems Analysis")
print("=" * 60)


# =====================================================
# 1. Plant model: second-order system
#
# G(s) = K_plant / (τ^2 s^2 + 2ζτ s + 1)
#
# Natural frequency ωn = 1/τ = 2 rad/s
# Open-loop damping   ζ_ol = 0.1 (lightly damped)
# DC gain             K_plant = 1.0
# =====================================================
print("\n[1] Plant: Second-order system")

omega_n_plant = 2.0    # rad/s — natural frequency
zeta_plant    = 0.1    # — open-loop damping (lightly damped)
K_plant       = 1.0    # — DC gain

print(f"\n  ωn = {omega_n_plant} rad/s,  ζ_ol = {zeta_plant},  K = {K_plant}")
print(f"  Open-loop step response characteristics:")

r_ol = anvil.R.second_order_metrics(omega_n=omega_n_plant, zeta=zeta_plant)
print(f"    Overshoot:  {r_ol['overshoot_pct']}%")
print(f"    t_settle:   {r_ol['t_settle']}  (2% criterion)")
print(f"    t_rise:     {r_ol['t_rise']}")
print(f"    t_peak:     {r_ol['t_peak']}")
print(f"    ωd:         {r_ol['omega_d']}")


# =====================================================
# 2. Ziegler-Nichols PID tuning
#
# Find the ultimate gain Ku by increasing proportional
# gain until sustained oscillations. Here we use a
# known value for the second-order plant.
# =====================================================
print("\n[2] Ziegler-Nichols PID Tuning")

# For this plant, ultimate gain and period are known analytically:
# Ku = (2*zeta*omega_n)^2 / (omega_n^2 * K_plant) * ... (simplified here)
# Using rule-of-thumb values for demonstration:
Ku = 12.0    # ultimate gain (proportional only, at onset of oscillation)
Tu = 2.2     # s — ultimate period

print(f"\n  Ultimate gain Ku = {Ku},  Ultimate period Tu = {Tu} s")
print(f"\n  Ziegler-Nichols tuning methods:")

for method in ["classic", "no_overshoot", "some_overshoot"]:
    r_zn = anvil.R.ziegler_nichols_pid(Ku=Ku, Tu=Tu, method=method)
    Kp = r_zn["Kp"].si if hasattr(r_zn["Kp"], "si") else r_zn["Kp"]
    Ti = r_zn["Ti"].si if hasattr(r_zn["Ti"], "si") else r_zn["Ti"]
    Td = r_zn["Td"].si if hasattr(r_zn["Td"], "si") else r_zn["Td"]
    print(f"  [{method:>15s}]  Kp={Kp:.3f}  Ti={Ti:.3f}s  Td={Td:.4f}s")

# Use classic Z-N as starting point
r_zn = anvil.R.ziegler_nichols_pid(Ku=Ku, Tu=Tu, method="classic")
def _v(x):
    return float(x.si) if hasattr(x, "si") else float(x)
Kp_zn = _v(r_zn["Kp"])
Ki_zn = _v(r_zn["Ki"])
Kd_zn = _v(r_zn["Kd"])


# =====================================================
# 3. Closed-loop step response via ODE simulation
#
# Plant: d²y/dt² + 2ζωn dy/dt + ωn² y = ωn² K_plant u
# PID:   u = Kp*e + Ki∫e dt + Kd*de/dt
# =====================================================
print("\n[3] Closed-loop step response simulation (PID)")

def closed_loop_ode(t, state, Kp, Ki, Kd, ref=1.0):
    """
    State: [y, dy_dt, integral_e]
    Plant: second-order + PID feedback
    """
    y, dydt, int_e = state
    e     = ref - y
    de_dt = -dydt   # de/dt = d(ref-y)/dt = -dy/dt (constant ref)
    u     = Kp * e + Ki * int_e + Kd * de_dt
    # Plant: d²y/dt² = ωn²(K_plant * u - y) - 2ζωn * dy/dt
    d2ydt2 = omega_n_plant**2 * (K_plant * u - y) - 2 * zeta_plant * omega_n_plant * dydt
    return [dydt, d2ydt2, e]

t_sim = np.linspace(0, 8, 1000)

# Open-loop step (Kp=1, Ki=0, Kd=0)
sol_ol = solvers.solve_ode(
    lambda t, s: closed_loop_ode(t, s, Kp=1.0, Ki=0.0, Kd=0.0),
    t_span=(0, 8), y0=[0.0, 0.0, 0.0], t_eval=t_sim, rtol=1e-8
)

# Z-N tuned PID
sol_zn = solvers.solve_ode(
    lambda t, s: closed_loop_ode(t, s, Kp=Kp_zn, Ki=Ki_zn, Kd=Kd_zn),
    t_span=(0, 8), y0=[0.0, 0.0, 0.0], t_eval=t_sim, rtol=1e-8
)

y_ol = sol_ol["y"][0]
y_zn = sol_zn["y"][0]

# Measure step response metrics
def step_metrics(t, y, ref=1.0, band=0.02):
    OS_pct = (y.max() - ref) / ref * 100 if y.max() > ref else 0.0
    settled = np.where(np.abs(y - ref) <= band * ref)[0]
    t_settle = t[settled[0]] if len(settled) else float("inf")
    above_half = np.where(y >= 0.5 * ref)[0]
    t_rise = t[above_half[0]] if len(above_half) else float("inf")
    return OS_pct, t_settle, t_rise

os_ol, ts_ol, tr_ol = step_metrics(t_sim, y_ol)
os_zn, ts_zn, tr_zn = step_metrics(t_sim, y_zn)

print(f"\n  Step response summary (unit step, 2% band):")
print(f"  {'Controller':>16s}  {'OS%':>6s}  {'t_settle(s)':>12s}  {'t_rise(s)':>10s}")
print(f"  {'P only (K=1)':>16s}  {os_ol:>6.1f}  {ts_ol:>12.3f}  {tr_ol:>10.3f}")
print(f"  {'Z-N PID':>16s}  {os_zn:>6.1f}  {ts_zn:>12.3f}  {tr_zn:>10.3f}")


# =====================================================
# 4. PID output RSQ — compute instantaneous control action
# =====================================================
print("\n[4] PID output RSQ")

pid_sys = System("pid_controller")
pid_sys.add("error",            0.35,     desc="Tracking error (rad)")
pid_sys.add("integral_error",   0.12,     desc="Integral of error (rad·s)")
pid_sys.add("derivative_error", -0.08,    desc="Derivative of error (rad/s)")
pid_sys.add("Kp",               Kp_zn,    desc="Proportional gain")
pid_sys.add("Ki",               Ki_zn,    desc="Integral gain")
pid_sys.add("Kd",               Kd_zn,    desc="Derivative gain")
pid_sys.use("pid_output")

r_pid = pid_sys.solve_forward()
result_u = r_pid["u_pid"].si if hasattr(r_pid["u_pid"], "si") else r_pid["u_pid"]
print(f"\n  Error = 0.35,  Integral = 0.12,  Derivative = -0.08")
print(f"  Z-N PID: Kp={Kp_zn:.3f},  Ki={Ki_zn:.3f},  Kd={Kd_zn:.4f}")
print(f"  Control action u = {result_u:.4f}")


# =====================================================
# 5. Stability check — Routh-Hurwitz (2nd order)
# =====================================================
print("\n[5] Routh-Hurwitz Stability Check")

print(f"\n  Characteristic polynomial: τ²s² + 2ζτs + 1  (2nd order)")
print(f"  Coefficients: a1 = 2ζ/ωn,  a0 = 1/ωn²")

test_cases = [
    ("Open-loop (ζ=0.1)",   2*0.1/omega_n_plant, 1/omega_n_plant**2),
    ("Negative damping",    -0.5,                  1.0),
    ("Unstable (a0<0)",      1.0,                 -1.0),
    ("Critically damped",    2/omega_n_plant,       1/omega_n_plant**2),
]

print(f"\n  {'Case':30s}  {'a1':>6s}  {'a0':>8s}  {'Stable?':>8s}")
print(f"  {'-'*60}")
for name, a1, a0 in test_cases:
    r_rh = anvil.R.routh_hurwitz_2nd(a1=a1, a0=a0)
    stable = r_rh["stable"]
    stable_v = stable if isinstance(stable, bool) else bool(stable)
    print(f"  {name:30s}  {a1:>6.3f}  {a0:>8.5f}  {'YES' if stable_v else 'NO':>8s}")


# =====================================================
# 6. Second-order metrics sweep — ωn and ζ trade study
# =====================================================
print("\n[6] Second-order metrics sweep — ζ trade study")

metrics_sys = System("step_response_design")
metrics_sys.add("omega_n", 5.0)   # rad/s — closed-loop natural frequency
metrics_sys.add("zeta",    0.7)   # damping ratio
metrics_sys.use("second_order_metrics")

print(f"\n  Sweep ζ at ωn = 5 rad/s:")
print(f"  {'ζ':>6s}  {'OS%':>8s}  {'t_settle(s)':>12s}  {'t_rise(s)':>10s}  {'BW(Hz)':>8s}")
print(f"  {'-'*52}")

for zeta in [0.3, 0.5, 0.7, 1.0, 1.5]:
    metrics_sys.set(zeta=zeta)
    r = metrics_sys.solve_forward()
    def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
    print(f"  {zeta:>6.2f}  {_v(r['overshoot_pct']):>8.1f}  "
          f"{_v(r['t_settle']):>12.4f}  {_v(r['t_rise']):>10.4f}  "
          f"{_v(r['bandwidth_Hz']) if 'bandwidth_Hz' in r else 0.0:>8.3f}")

sweep_zeta = metrics_sys.sweep("zeta", np.linspace(0.2, 2.0, 10))
sweep_zeta.summary(outputs=["overshoot_pct", "t_settle", "t_rise", "omega_d"])

print(f"\n  Design choice: ζ = 0.7 balances OS% and t_settle (classic choice).")


# =====================================================
# 7. First-order step response RSQ
# =====================================================
print("\n[7] First-order step response metrics")

fo_sys = System("first_order_control")
fo_sys.add("K",        2.0,   desc="DC gain")
fo_sys.add("tau",      0.5,   desc="Time constant (s)")
fo_sys.use("first_order_step")

r_fo = fo_sys.solve_forward()
def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
print(f"\n  Plant: K={2.0}, τ={0.5}s")
print(f"    Settling time (2%): {_v(r_fo['t_settle']):.3f} s")
print(f"    Rise time:          {_v(r_fo['t_rise']):.3f} s")
print(f"    Bandwidth:          {_v(r_fo['bandwidth_Hz']):.3f} Hz")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
