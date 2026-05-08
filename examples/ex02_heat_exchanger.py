"""
Example 2: Heat Exchanger Design (Coupled System)
==================================================

Demonstrates:
    - Building a System with coupled (circular) dependencies
    - Gauss-Seidel iterative solver with under-relaxation
    - Convergence monitoring
    - diagnose() for pre-solve checks

Engineering context:
    Counter-flow heat exchanger: hot exhaust gas heats cold water.
    T_hot_out depends on T_cold_out and vice versa -- a coupled problem.
"""

import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anvil import Q, System
from anvil.monitor import diagnose

print("=" * 60)
print("  Example 2: Counter-Flow Heat Exchanger")
print("=" * 60)

# --- Physics ---

def hot_side(T_hot_in, T_cold_out, UA, Cp_hot, mdot_hot):
    """Hot fluid energy balance using LMTD approximation."""
    # Simplified: Q = UA * mean temperature difference
    delta_T_mean = (T_hot_in - T_cold_out) * 0.5
    Q_dot = UA * delta_T_mean
    T_hot_out = T_hot_in - Q_dot / (mdot_hot * Cp_hot)
    return {"T_hot_out": Q(T_hot_out, "K"), "Q_dot": Q(Q_dot, "W")}

def cold_side(T_cold_in, Q_dot, Cp_cold, mdot_cold):
    """Cold fluid energy balance."""
    T_cold_out = T_cold_in + Q_dot / (mdot_cold * Cp_cold)
    return {"T_cold_out": Q(T_cold_out, "K")}

def effectiveness(T_hot_in, T_hot_out, T_cold_in):
    """Heat exchanger effectiveness: actual / maximum possible."""
    eps = (T_hot_in - T_hot_out) / (T_hot_in - T_cold_in + 1e-10)
    return {"effectiveness": eps}

# --- Build the system ---

hx = System("counter_flow_hx")

# Operating conditions
hx.add("T_hot_in",  600,    "K",      desc="Hot inlet (exhaust gas)")
hx.add("T_cold_in", 290,    "K",      desc="Cold inlet (water)")
hx.add("UA",        2000,   "W",      desc="Overall heat transfer coefficient * area")
hx.add("Cp_hot",    1050,   "J/kg/K", desc="Hot fluid specific heat (exhaust)")
hx.add("Cp_cold",   4186,   "J/kg/K", desc="Cold fluid specific heat (water)")
hx.add("mdot_hot",  0.8,    "kg/s",   desc="Hot mass flow rate")
hx.add("mdot_cold", 0.5,    "kg/s",   desc="Cold mass flow rate")

# Initial guesses for coupled variables
hx.add("T_cold_out", 350,   "K",      desc="Cold outlet (initial guess)")
hx.add("Q_dot",      50000, "W",      desc="Heat transfer rate (initial guess)")

hx.use(hot_side)
hx.use(cold_side)
hx.use(effectiveness)

# --- Pre-solve diagnostics ---
print("\n[1] Pre-solve diagnostics:")
for msg in diagnose(hx):
    print(f"  {msg}")

# --- Solve ---
print("\n[2] Solving (Gauss-Seidel with monitoring)...")
result = hx.solve_gauss_seidel(
    max_iter=200,
    rtol=1e-10,
    relaxation=0.5,
    monitor=True,
    verbose=True,
)
result.summary()

# --- Verify energy balance ---
print("\n[3] Energy balance check:")
Q_hot  = result["mdot_hot"].si * result["Cp_hot"].si * (result["T_hot_in"].si - result["T_hot_out"].si)
Q_cold = result["mdot_cold"].si * result["Cp_cold"].si * (result["T_cold_out"].si - result["T_cold_in"].si)
print(f"  Q_hot  = {Q_hot:.2f} W")
print(f"  Q_cold = {Q_cold:.2f} W")
print(f"  Error  = {abs(Q_hot - Q_cold):.4f} W")
print(f"  Effectiveness = {result['effectiveness'].si:.4f}")

# --- Convergence info ---
hist = hx.history()
print(f"\n[4] Convergence: {len(hist)} iterations")
print(f"  Initial residual: {hist[0]['residual']:.2e}")
print(f"  Final residual:   {hist[-1]['residual']:.2e}")

# --- Sweep: vary UA ---
print("\n[5] Sweep: effectiveness vs UA...")
sweep = hx.sweep("UA", np.linspace(500, 5000, 6),
                 method="gauss_seidel", relaxation=0.5, max_iter=200)
sweep.summary(outputs=["effectiveness", "T_hot_out", "T_cold_out", "Q_dot"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
