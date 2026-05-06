"""
Example: 2D Euler CFD — Supersonic flow over a wedge
=====================================================

Inviscid supersonic flow (M=2) over a 10-degree wedge.
Demonstrates:
    1. Analytical oblique shock solution (exact, instant)
    2. Numerical solution via anvil.cfd (2D Euler FV solver)
    3. Comparison of shock angle and pressure ratio
    4. Mach sweep using the solver as an Anvil Relation
    5. ParaView and Tecplot output
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh
from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall, Farfield
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# ─────────────────────────────────────────────────────────────────
# PART 1 — Analytical oblique shock (exact solution)
# ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("  PART 1: Analytical oblique shock solution")
print("=" * 60)

M_inf      = 2.0
theta_deg  = 10.0        # wedge half-angle
gamma      = 1.4
p_inf      = 101325.0    # Pa
T_inf      = 300.0       # K
R_gas      = 287.058     # J/kg/K

r = anvil.R.oblique_shock(M1=M_inf, theta_deg=theta_deg, gamma=gamma)
print(f"\n  Freestream M = {M_inf},  wedge half-angle = {theta_deg} deg")
print(f"  Shock attached: {r['attached']}")
print(f"  Shock angle beta = {r['beta_deg']:.3f} deg  (Mach angle = {np.degrees(np.arcsin(1/M_inf)):.3f} deg)")
print(f"  Downstream M2   = {r['M2']:.4f}")
print(f"  p2/p1           = {r['p2_p1']:.4f}")
print(f"  T2/T1           = {r['T2_T1']:.4f}")
print(f"  rho2/rho1       = {r['rho2_rho1']:.4f}")

# Downstream conditions
p2   = p_inf   * r['p2_p1']
T2   = T_inf   * r['T2_T1']
rho2 = (p_inf / (R_gas * T_inf)) * r['rho2_rho1']
print(f"\n  Downstream: p = {p2:.1f} Pa,  T = {T2:.1f} K,  M = {r['M2']:.4f}")

# ─────────────────────────────────────────────────────────────────
# PART 2 — Numerical solution: anvil.cfd 2D Euler solver
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Numerical 2D Euler solution")
print("=" * 60)

# Build body-fitted wedge mesh
# Domain: x in [0, 1] m,  y from wedge surface up to 0.6 m above
mesh = Mesh.wedge(
    half_angle_deg = theta_deg,
    chord          = 1.0,     # m
    height         = 0.6,     # m above wedge surface
    nx             = 80,
    ny             = 40,
)
mesh.info()

# Boundary conditions
bcs = {
    "west":  SupersonicInlet(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
    "east":  SupersonicOutlet(),
    "south": SlipWall(),                            # wedge surface (inviscid)
    "north": Farfield(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
}

# Solver: 2nd-order Roe with MUSCL, local time stepping, RK4
solver = CFDSolver(
    mesh        = mesh,
    bcs         = bcs,
    gamma       = gamma,
    R_gas       = R_gas,
    flux_scheme = "roe",      # Roe approximate Riemann solver
    order       = 2,          # MUSCL + van Leer limiter
    time_scheme = "rk4",      # 4-stage Runge-Kutta
    cfl         = 0.4,        # CFL number (reduce if diverging)
    transient   = False,      # local time stepping for steady-state
)
solver.initialize(M=M_inf, p=p_inf, T=T_inf, alpha_deg=0.0)

# Run solver — watch residuals converge
print(f"\n  Running Euler solver ({mesh.nx}x{mesh.ny} cells, Roe flux, 2nd order)...")
result = solver.run(
    max_iter    = 3000,
    tol         = 1e-5,
    monitor     = True,
    verbose     = True,
    print_every = 200,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3 — Comparison: analytical vs numerical
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Analytical vs Numerical comparison")
print("=" * 60)

# Sample downstream region (right half of domain, above wall)
nx, ny = mesh.nx, mesh.ny
ds_i   = slice(nx // 2, nx)     # downstream half
ds_j   = slice(ny // 4, ny // 2)  # mid-domain height

M_ds   = result.M[ds_i, ds_j].mean()
p_ds   = result.p[ds_i, ds_j].mean()
T_ds   = result.T[ds_i, ds_j].mean()

print(f"\n  Downstream region (x=[0.5,1.0], mid-height):")
print(f"  {'':20s}  {'Analytical':>12s}  {'Numerical':>12s}  {'Error %':>9s}")
print(f"  {'p2 [Pa]':20s}  {p2:>12.2f}  {p_ds:>12.2f}  {abs(p_ds-p2)/p2*100:>8.2f}%")
print(f"  {'T2 [K]':20s}  {T2:>12.3f}  {T_ds:>12.3f}  {abs(T_ds-T2)/T2*100:>8.2f}%")
print(f"  {'M2':20s}  {r['M2']:>12.4f}  {M_ds:>12.4f}  {abs(M_ds-r['M2'])/r['M2']*100:>8.2f}%")
print(f"\n  (numerical error expected ~1-5% at this resolution)")

# ─────────────────────────────────────────────────────────────────
# PART 4 — Write output files for ParaView and Tecplot
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Writing output files")
print("=" * 60)

out_dir = os.path.dirname(__file__)
result.to_vtk(     os.path.join(out_dir, "wedge_flow.vtk"))
result.to_tecplot( os.path.join(out_dir, "wedge_flow.dat"))
result.to_restart( os.path.join(out_dir, "wedge_restart.npz"))
print("  -> Open wedge_flow.vtk in ParaView (File -> Open, then Apply)")
print("  -> Open wedge_flow.dat in Tecplot (Data -> Load Data File)")

# ─────────────────────────────────────────────────────────────────
# PART 5 — Mach sweep using solver as Anvil Relation
#           Runs each Mach number in parallel threads
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 5: Mach number sweep (solver as Anvil Relation)")
print("=" * 60)

# Wrap solver as a Relation: M_inf -> M_max, p_wall
cfd_rel = solver.as_relation(
    inputs  = ["M_inf", "p_inf", "T_inf"],
    outputs = ["M_max", "p_wall"],
    name    = "wedge_euler",
)

# Build a simple System around it
sweep_sys = anvil.system("wedge_mach_sweep")
sweep_sys.add("M_inf",  2.0)
sweep_sys.add("p_inf",  p_inf)
sweep_sys.add("T_inf",  T_inf)
sweep_sys.use(cfd_rel)

print("\n  Sweeping M = 1.5, 2.0, 2.5, 3.0  (parallel=2)...")
mach_vals = np.array([1.5, 2.0, 2.5, 3.0])
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2,
                         skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# Compare with analytical
print("\n  Analytical comparison:")
print(f"  {'M_inf':>8s}  {'beta [deg]':>12s}  {'p_wall/p_inf':>14s}")
for M in mach_vals:
    r_a = anvil.R.oblique_shock(M1=float(M), theta_deg=theta_deg, gamma=gamma)
    if r_a["attached"]:
        print(f"  {M:>8.1f}  {r_a['beta_deg']:>12.3f}  {r_a['p2_p1']:>14.4f}")
    else:
        print(f"  {M:>8.1f}  {'(detached)':>12s}  {'---':>14s}")

# Cleanup output files
for f in ["wedge_flow.vtk", "wedge_flow.dat", "wedge_restart.npz"]:
    fpath = os.path.join(out_dir, f)
    if os.path.exists(fpath):
        os.remove(fpath)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
print("""
  CFD solver architecture summary:
    Scheme:    2D cell-centred finite volume (ghost cells)
    Flux:      Roe approximate Riemann solver (with Harten entropy fix)
    Order:     2nd order MUSCL + van Leer limiter
    Time:      4-stage Runge-Kutta, local time stepping
    BCs:       SupersonicInlet, SupersonicOutlet, SlipWall, Farfield
    Output:    VTK legacy (.vtk, ParaView), Tecplot ASCII (.dat)

  Extensible to:
    - Viscous flows: add viscous_flux_2d() in flux.py
    - 3D:           add k-index in mesh and w-velocity in state
    - CLI adapter:  wrap solver in Adapter("su2_cfd", backend="cli", ...)
""")
