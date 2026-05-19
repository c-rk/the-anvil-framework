"""
Example: Differential Equations in Anvil
=========================================

Shows three patterns for using differential equations within the framework:

  Pattern A -- Direct: standalone ODE, no System involved.
              Use when: purely time/space-driven problem with fixed params.

  Pattern B -- ODE inside a Relation: the Relation calls solve_ode internally
              and returns summary scalars that feed into the rest of a System.
              Use when: ODE parameters come from other equations / inputs.

  Pattern C -- ODE + algebraic coupling: an ODE feeds a steady-state System,
              whose outputs feed back into defining the ODE. Uses Gauss-Seidel.

Problems used:
  A -- Radioactive decay chain  (dy/dt = f(y))
  B -- Rocket gravity turn trajectory (ODE inside a Relation in a System)
  C -- Heat soak: ODE temperature history feeds a material property System
"""

import sys, os

import numpy as np
import anvil
from anvil import Q, solvers

print("=" * 60)
print("  Pattern A -- Direct ODE (no System)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN A: call solve_ode directly.
#
# Problem: two-species radioactive decay chain
#   dN1/dt = -λ1 * N1
#   dN2/dt =  λ1 * N1  -  λ2 * N2
#
# Write the RHS as a plain function f(t, y) -> dy/dt.
# Call solvers.solve_ode() with the method named explicitly.
# ─────────────────────────────────────────────────────────────────

lambda1 = 0.05    # 1/s  (parent decay constant)
lambda2 = 0.10    # 1/s  (daughter decay constant)
N0      = [1000.0, 0.0]  # initial populations

def decay_rhs(t, y):
    N1, N2 = y
    return [
        -lambda1 * N1,
         lambda1 * N1 - lambda2 * N2,
    ]

result = solvers.solve_ode(
    decay_rhs,
    t_span=(0, 60),
    y0=N0,
    method="RK45",         # explicit -- good for non-stiff problems
    t_eval=np.linspace(0, 60, 300),
    rtol=1e-8,
    atol=1e-10,
    verbose=True,
)

t   = result["t"]
N1  = result["y"][0]
N2  = result["y"][1]

print(f"\n  At t=60 s:")
print(f"    N1 = {N1[-1]:.2f}  (expect {N0[0]*np.exp(-lambda1*60):.2f})")
print(f"    N2 = {N2[-1]:.2f}")
print(f"    Peak N2 at t = {t[np.argmax(N2)]:.2f} s")

# result["sol"] is the scipy OdeResult; .sol is the dense callable
print(f"    N1 at t=10 s (dense): {result['sol'].sol(10)[0]:.2f}")


print("\n" + "=" * 60)
print("  Pattern B -- ODE inside a Relation (System integration)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN B: wrap the ODE call inside a Relation.
#
# Problem: vertical rocket burn.
#   dv/dt = F_thrust/m - g - (0.5*Cd*A*rho*v^2)/m
#   dm/dt = -mdot
#   dh/dt = v
#
# The Relation takes design parameters, integrates the ODE,
# returns summary scalars (burnout velocity, peak altitude).
# These scalars can then feed other Relations in the same System.
# ─────────────────────────────────────────────────────────────────

def rocket_burn(F_thrust, mdot, Cd, A_ref, m_dry, m_prop, rho_air=1.225, g=9.81):
    """
    Integrate vertical rocket burn ODE from liftoff to burnout.
    Returns peak velocity, burnout altitude, burnout time.
    """
    m0       = m_dry + m_prop
    t_burn   = m_prop / mdot           # burnout time

    def rhs(t, state):
        v, h, m = state
        if m <= m_dry:
            # coast phase -- no thrust
            F = 0.0
            dm = 0.0
        else:
            F  = F_thrust
            dm = -mdot

        drag  = 0.5 * Cd * A_ref * rho_air * v * abs(v)
        dvdt  = (F - drag) / m - g
        dhdt  = v
        dmdt  = dm
        return [dvdt, dhdt, dmdt]

    # Event: burnout (mass reaches m_dry)
    def burnout(t, state):
        return state[2] - m_dry
    burnout.terminal  = True
    burnout.direction = -1

    sol = solvers.solve_ode(
        rhs,
        t_span=(0, t_burn * 1.5),    # generous span; event stops it
        y0=[0.0, 0.0, m0],
        method="RK45",
        events=burnout,
        rtol=1e-7,
        atol=1e-9,
    )

    v_burnout = float(sol["y"][0, -1])
    h_burnout = float(sol["y"][1, -1])
    t_burnout = float(sol["t"][-1])

    return {
        "v_burnout":  Q(v_burnout, "m/s"),
        "h_burnout":  Q(h_burnout, "m"),
        "t_burnout":  Q(t_burnout, "s"),
        "delta_v":    Q(v_burnout, "m/s"),   # no gravity / drag: Tsiolkovsky would give more
    }


def coast_to_apogee(v_burnout, h_burnout, g=9.81):
    """After burnout, coast phase: v^2 = v0^2 - 2*g*dh."""
    dh_coast = v_burnout**2 / (2 * g)
    h_apogee = h_burnout + dh_coast
    return {
        "dh_coast":  Q(dh_coast, "m"),
        "h_apogee":  Q(h_apogee, "m"),
    }


# Build the System -- ODE Relation sits alongside algebraic Relation
rocket = anvil.system("sounding_rocket")
rocket.add("F_thrust",  10000, "N",    desc="Thrust")
rocket.add("mdot",        5.0, "kg/s", desc="Mass flow rate")
rocket.add("Cd",          0.3,         desc="Drag coefficient")
rocket.add("A_ref",      0.02, "m^2",  desc="Reference area")
rocket.add("m_dry",      20.0, "kg",   desc="Dry mass")
rocket.add("m_prop",     30.0, "kg",   desc="Propellant mass")

rocket.use(rocket_burn)       # ODE inside -- solves internally, returns scalars
rocket.use(coast_to_apogee)   # algebraic -- uses burnout scalars from ODE above

result = rocket.solve_forward()
result.summary(keys=["F_thrust", "m_dry", "m_prop",
                      "v_burnout", "h_burnout", "t_burnout", "h_apogee"])

print(f"\n  Apogee: {result['h_apogee'].to('km').value:.3f} km")
print(f"  Burnout velocity: {result['v_burnout'].value:.1f} m/s")


print("\n" + "=" * 60)
print("  Pattern B -- Sweep over propellant mass")
print("=" * 60)

# Sweep works normally -- the ODE re-integrates for each point
sweep = rocket.sweep("m_prop", np.linspace(10, 60, 8), parallel=4)
sweep.summary(outputs=["v_burnout", "h_burnout", "h_apogee"])


print("\n" + "=" * 60)
print("  Pattern C -- Stiff ODE (combustion kinetics stub)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN C: use solve_ode_stiff for stiff problems.
#
# Problem: simplified A -> B -> C kinetics (two-step first-order)
#   The second step is 1000× faster -> stiff system.
#   RK45 would need tiny steps; BDF handles it efficiently.
# ─────────────────────────────────────────────────────────────────

k1 = 1.0      # slow step A -> B
k2 = 1000.0   # fast step B -> C  (stiffness ratio = 1000)

def kinetics_rhs(t, y):
    A, B, C = y
    return [
        -k1 * A,
         k1 * A - k2 * B,
         k2 * B,
    ]

sol_stiff = solvers.solve_ode_stiff(
    kinetics_rhs,
    t_span=(0, 5),
    y0=[1.0, 0.0, 0.0],
    method="BDF",          # implicit -- handles stiff systems efficiently
    t_eval=np.linspace(0, 5, 200),
    rtol=1e-6,
    atol=1e-10,
    verbose=True,
)

A_final = sol_stiff["y"][0, -1]
C_final = sol_stiff["y"][2, -1]
print(f"\n  At t=5 s:")
print(f"    A = {A_final:.6f}  (expect {np.exp(-k1*5):.6f})")
print(f"    C = {C_final:.6f}  (expect ~{1 - np.exp(-k1*5):.6f})")
print(f"    Steps taken: {sol_stiff['nfev']} RHS evaluations")
print(f"    (RK45 would need ~{int(k2*5/1e-4):,} steps to stay stable)")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
print("""
  Summary of patterns:

  Pattern A -- Direct solve_ode / solve_ode_stiff / solve_bvp call.
    When: self-contained ODE, fixed parameters, time-history output.
    How:  write f(t, y), call solvers.solve_ode(..., method="RK45").

  Pattern B -- ODE wrapped inside a Relation.
    When: ODE parameters come from inputs or other equations in a System.
    How:  Relation takes scalar inputs -> calls solve_ode inside -> returns
          scalar summary outputs -> feeds rest of System normally.
          Sweep, sensitivity analysis, and composition all work.

  Pattern C -- Stiff ODE.
    Same as A or B, but use solve_ode_stiff(..., method="BDF").
    BDF/Radau handle k_fast/k_slow >> 1 without tiny step sizes.

  Why not put RHS in the registry?
    The RHS function (f(t,y)) is problem-specific physics -- it CAN be
    registered as an RSQ if you want to reuse it:
      anvil.push(decay_rhs, domain="nuclear", tags=["decay", "ODE"])
    But solve_ode itself is math machinery, not physics -- it stays in
    anvil.solvers, callable anywhere.
""")
